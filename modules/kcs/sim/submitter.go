// YAML-driven submitter for the pfn k8s-cluster-simulator.
//
// The upstream example hard-codes a random workload in Go. This submitter reads
// the toolkit's standard pods-<N>.yaml (Alibaba-derived k8s Pods) and submits
// every pod once at clock 0, synthesising the "simSpec" annotation the simulator
// needs (one execution phase of --duration seconds at the pod's requested
// resources). After submitting the batch it terminates itself, so KubeSim.Run
// returns once the cluster drains.
//
// Two options make the workload match the other tools of the toolkit:
//   - gpu=false drops the GPU annotations (the other tools only see CPU and
//     memory requests);
//   - horizon>0 keeps the submitter alive and cancels the simulation once the
//     simulated clock has advanced horizon seconds. With a --duration longer
//     than the horizon no pod finishes, so the pods still pending at the end are
//     the pods kcs could not place, as for the tools that run a control plane.
//     Without it (horizon=0, the default) the run ends only when every pod has
//     run and finished, so no pod is ever left pending.
package main

import (
	"context"
	"io"
	"os"
	"time"

	yaml "gopkg.in/yaml.v2"
	v1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/kubernetes/pkg/scheduler/algorithm"

	"github.com/containerd/containerd/log"
	"github.com/pfnet-research/k8s-cluster-simulator/pkg/clock"
	"github.com/pfnet-research/k8s-cluster-simulator/pkg/metrics"
	"github.com/pfnet-research/k8s-cluster-simulator/pkg/submitter"
)

// rawPod is the minimal subset of a k8s Pod manifest we need.
type rawPod struct {
	Metadata struct {
		Name        string            `yaml:"name"`
		Namespace   string            `yaml:"namespace"`
		Annotations map[string]string `yaml:"annotations"`
	} `yaml:"metadata"`
	Spec struct {
		Containers []struct {
			Resources struct {
				Requests map[string]string `yaml:"requests"`
				Limits   map[string]string `yaml:"limits"`
			} `yaml:"resources"`
		} `yaml:"containers"`
	} `yaml:"spec"`
}

type yamlSubmitter struct {
	pods    []*v1.Pod
	done    bool
	horizon time.Duration
	cancel  context.CancelFunc
	start   clock.Clock
}

func newYAMLSubmitter(podsPath string, durationSec int, useGPU bool,
	horizonSec int, cancel context.CancelFunc) *yamlSubmitter {

	f, err := os.Open(podsPath)
	if err != nil {
		log.L.WithError(err).Fatalf("cannot open pods file %s", podsPath)
	}
	defer f.Close()

	pods := []*v1.Pod{}
	dec := yaml.NewDecoder(f)
	idx := 0
	for {
		var r rawPod
		err := dec.Decode(&r)
		if err == io.EOF {
			break
		}
		if err != nil || len(r.Spec.Containers) == 0 {
			continue
		}
		if !useGPU {
			delete(r.Metadata.Annotations, "nvidia.com/gpu")
			delete(r.Metadata.Annotations, "alibabacloud.com/gpu-count")
		}
		p := buildPod(r, idx, durationSec)
		if p != nil {
			pods = append(pods, p)
			idx++
		}
	}
	log.L.Infof("yamlSubmitter: loaded %d pods from %s (gpu=%v, horizon=%ds)",
		len(pods), podsPath, useGPU, horizonSec)
	return &yamlSubmitter{
		pods:    pods,
		horizon: time.Duration(horizonSec) * time.Second,
		cancel:  cancel,
	}
}

func (s *yamlSubmitter) Submit(
	clk clock.Clock, _ algorithm.NodeLister, _ metrics.Metrics) ([]submitter.Event, error) {

	if s.done {
		// Horizon mode: the submitter stays registered so that it sees the
		// clock, and stops the simulation once the horizon has passed.
		if s.horizon > 0 && clk.Sub(s.start) >= s.horizon {
			s.cancel()
		}
		return []submitter.Event{}, nil
	}
	s.done = true
	s.start = clk
	events := make([]submitter.Event, 0, len(s.pods)+1)
	for _, p := range s.pods {
		events = append(events, &submitter.SubmitEvent{Pod: p})
	}
	if s.horizon == 0 {
		events = append(events, &submitter.TerminateSubmitterEvent{})
	}
	return events, nil
}

// gpuFromAnnotations extracts a GPU count from Alibaba annotations.
func gpuFromAnnotations(ann map[string]string) string {
	for _, k := range []string{"nvidia.com/gpu", "alibabacloud.com/gpu-count"} {
		if v, ok := ann[k]; ok && v != "" {
			return v
		}
	}
	return ""
}

func toResourceList(m map[string]string, gpu string) v1.ResourceList {
	rl := v1.ResourceList{}
	for k, v := range m {
		if k == "ephemeral-storage" {
			continue
		}
		if q, err := resource.ParseQuantity(v); err == nil {
			rl[v1.ResourceName(k)] = q
		}
	}
	if gpu != "" {
		if q, err := resource.ParseQuantity(gpu); err == nil {
			rl["nvidia.com/gpu"] = q
		}
	}
	return rl
}

func buildPod(r rawPod, idx, durationSec int) *v1.Pod {
	name := r.Metadata.Name
	if name == "" {
		name = "pod-" + itoa(idx)
	}
	ns := r.Metadata.Namespace
	if ns == "" {
		ns = "default"
	}
	c := r.Spec.Containers[0]
	gpu := gpuFromAnnotations(r.Metadata.Annotations)
	req := toResourceList(c.Resources.Requests, gpu)
	lim := toResourceList(c.Resources.Limits, gpu)
	if len(lim) == 0 {
		lim = req
	}

	// simSpec: one phase running for durationSec at the requested usage.
	cpu := pick(c.Resources.Requests["cpu"], "1")
	mem := pick(c.Resources.Requests["memory"], "1Gi")
	gpuUsage := pick(gpu, "0")
	simSpec := "- seconds: " + itoa(durationSec) + "\n" +
		"  resourceUsage:\n" +
		"    cpu: \"" + cpu + "\"\n" +
		"    memory: \"" + mem + "\"\n" +
		"    nvidia.com/gpu: \"" + gpuUsage + "\"\n"

	prio := int32(0)
	return &v1.Pod{
		TypeMeta: metav1.TypeMeta{APIVersion: "v1", Kind: "Pod"},
		ObjectMeta: metav1.ObjectMeta{
			Name:        name,
			Namespace:   ns,
			Annotations: map[string]string{"simSpec": simSpec},
		},
		Spec: v1.PodSpec{
			Priority: &prio,
			Containers: []v1.Container{{
				Name:      "container",
				Image:     "container",
				Resources: v1.ResourceRequirements{Requests: req, Limits: lim},
			}},
		},
	}
}

func pick(v, def string) string {
	if v == "" {
		return def
	}
	return v
}

func itoa(i int) string {
	if i == 0 {
		return "0"
	}
	neg := i < 0
	if neg {
		i = -i
	}
	buf := [20]byte{}
	pos := len(buf)
	for i > 0 {
		pos--
		buf[pos] = byte('0' + i%10)
		i /= 10
	}
	if neg {
		pos--
		buf[pos] = '-'
	}
	return string(buf[pos:])
}
