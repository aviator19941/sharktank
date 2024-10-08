// Copyright 2024 Advanced Micro Devices, Inc
//
// Licensed under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#ifndef SHORTFIN_WORKER_H
#define SHORTFIN_WORKER_H

#include <functional>
#include <string>
#include <vector>

#include "iree/base/loop_sync.h"
#include "shortfin/local/async.h"
#include "shortfin/support/api.h"
#include "shortfin/support/iree_concurrency.h"

namespace shortfin::local {

// Cooperative worker.
class SHORTFIN_API Worker {
 public:
  struct Options {
    iree_allocator_t allocator;
    std::string name;

    // Controls the maximum duration that can transpire between the loop
    // making an outer trip where it can exit and perform other outside-world
    // maintenance. Without this, the loop could run forever if there was
    // an infinite/long async wait or something.
    iree_timeout_t quantum = iree_make_timeout_ms(500);

    // Whether to create the worker on an owned thread. If false, then the
    // worker is set up to be adopted and a thread will not be created.
    bool owned_thread = true;

    Options(iree_allocator_t allocator, std::string name)
        : allocator(allocator), name(name) {}
  };
  using Factory = std::function<std::unique_ptr<Worker>(Options options)>;

  Worker(Options options);
  Worker(const Worker &) = delete;
  virtual ~Worker();

  const Options &options() const { return options_; }
  const std::string_view name() const { return options_.name; }
  std::string to_s();

  void Start();
  void Kill();
  virtual void WaitForShutdown();

  // Runs on the current thread. This is used instead of Start() when
  // owned_thread is false.
  void RunOnCurrentThread();

  // Enqueues a callback to the worker from another thread.
  void CallThreadsafe(std::function<void()> callback);

  // Operations that can be done from on the worker.
  // Callback to execute user code on the loop "soon". This variant must not
  // raise exceptions and matches the underlying C API. It should not generally
  // be used by "regular users" but can be useful for bindings that wish to
  // reduce the tolls/hops.
  iree_status_t CallLowLevel(
      iree_status_t (*callback)(void *user_data, iree_loop_t loop,
                                iree_status_t status) noexcept,
      void *user_data,
      iree_loop_priority_e priority = IREE_LOOP_PRIORITY_DEFAULT) noexcept;

  // Calls back after a timeout.
  iree_status_t WaitUntilLowLevel(
      iree_timeout_t timeout,
      iree_status_t (*callback)(void *user_data, iree_loop_t loop,
                                iree_status_t status) noexcept,
      void *user_data);

  // Calls back once a wait_source is satisfied.
  iree_status_t WaitOneLowLevel(
      iree_wait_source_t wait_source, iree_timeout_t timeout,
      iree_status_t (*callback)(void *user_data, iree_loop_t loop,
                                iree_status_t status) noexcept,
      void *user_data);

  // Time management.
  // Returns the current absolute time in nanoseconds.
  iree_time_t now();
  iree_time_t ConvertRelativeTimeoutToDeadlineNs(iree_duration_t timeout_ns);

 protected:
  virtual void OnThreadStart();
  virtual void OnThreadStop();

 private:
  int RunOnThread();
  iree_status_t ScheduleExternalTransactEvent();
  iree_status_t TransactLoop(iree_status_t signal_status);

  const Options options_;
  iree::slim_mutex mu_;
  iree::thread_ptr thread_;
  iree::event signal_transact_;
  iree::event signal_ended_;

  // State management. These are all manipulated both on and off the worker
  // thread.
  std::vector<std::function<void()>> pending_thunks_;
  bool kill_ = false;
  bool has_run_ = false;

  // Loop management. This is all purely operated on the worker thread.
  iree_loop_sync_scope_t loop_scope_;
  iree_loop_sync_t *loop_sync_;
  iree_loop_t loop_;
  std::vector<std::function<void()>> next_thunks_;
};

}  // namespace shortfin::local

#endif  // SHORTFIN_WORKER_H
