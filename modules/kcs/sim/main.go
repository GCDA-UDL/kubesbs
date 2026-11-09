// Custom entry point for the pfn k8s-cluster-simulator that drives a workload
// read from a YAML file (the toolkit's pods-<N>.yaml) instead of the hard-coded
// random submitter in the upstream example. Cluster nodes + metrics loggers come
// from the --config file (see modules/kcs/module.sh, which generates it).
//
// Build: this file replaces the upstream example package; see
// modules/kcs/build.sh. Termination: by default KubeSim.Run returns when the
// submitter has terminated and the cluster has drained (every pod has run and
// finished); with --horizon the submitter cancels the run after that many
// simulated seconds (see submitter.go).
package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"github.com/containerd/containerd/log"
	"github.com/pkg/errors"
	"github.com/spf13/cobra"
	"k8s.io/kubernetes/pkg/scheduler/algorithm/predicates"
	"k8s.io/kubernetes/pkg/scheduler/algorithm/priorities"

	kubesim "github.com/pfnet-research/k8s-cluster-simulator/pkg"
	"github.com/pfnet-research/k8s-cluster-simulator/pkg/queue"
	"github.com/pfnet-research/k8s-cluster-simulator/pkg/scheduler"
)

var (
	configPath  string
	podsPath    string
	durationSec int
	useGPU      bool
	horizonSec  int
)

func main() {
	if err := rootCmd.Execute(); err != nil {
		log.L.WithError(err).Fatal("Error executing root command")
	}
}

func init() {
	rootCmd.PersistentFlags().StringVar(&configPath, "config", "config", "config file (excluding extension)")
	rootCmd.PersistentFlags().StringVar(&podsPath, "pods", "pods.yaml", "pods YAML workload file")
	rootCmd.PersistentFlags().IntVar(&durationSec, "duration", 300, "simulated run seconds per pod")
	rootCmd.PersistentFlags().BoolVar(&useGPU, "gpu", true,
		"turn the pods' GPU annotations into nvidia.com/gpu requests")
	rootCmd.PersistentFlags().IntVar(&horizonSec, "horizon", 0,
		"stop after this many simulated seconds (0: run until every pod has finished)")
}

var rootCmd = &cobra.Command{
	Use:   "kcs-yamlsim",
	Short: "pfn k8s-cluster-simulator driven by a YAML pod workload.",
	Run: func(cmd *cobra.Command, args []string) {
		ctx, cancel := newInterruptableContext()

		q := queue.NewPriorityQueue()
		sched := buildScheduler()
		ksim := kubesim.NewKubeSimFromConfigPathOrDie(configPath, q, sched)
		ksim.AddSubmitter("YAMLSubmitter",
			newYAMLSubmitter(podsPath, durationSec, useGPU, horizonSec, cancel))

		if err := ksim.Run(ctx); err != nil && errors.Cause(err) != context.Canceled {
			log.L.Fatal(err)
		}
	},
}

func buildScheduler() scheduler.Scheduler {
	sched := scheduler.NewGenericScheduler(true)
	sched.AddPredicate("GeneralPredicates", predicates.GeneralPredicates)
	sched.AddPrioritizer(priorities.PriorityConfig{
		Name: "BalancedResourceAllocation", Map: priorities.BalancedResourceAllocationMap, Weight: 1,
	})
	sched.AddPrioritizer(priorities.PriorityConfig{
		Name: "LeastRequested", Map: priorities.LeastRequestedPriorityMap, Weight: 1,
	})
	return &sched
}

func newInterruptableContext() (context.Context, context.CancelFunc) {
	ctx, cancel := context.WithCancel(context.Background())
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sig
		cancel()
	}()
	return ctx, cancel
}
