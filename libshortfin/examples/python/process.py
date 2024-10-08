#!/usr/bin/env python
# Copyright 2024 Advanced Micro Devices, Inc
#
# Licensed under the Apache License v2.0 with LLVM Exceptions.
# See https://llvm.org/LICENSE.txt for license information.
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import asyncio
import threading

import shortfin as sf

lsys = sf.host.CPUSystemBuilder().create_system()


class MyProcess(sf.Process):
    def __init__(self, arg, **kwargs):
        super().__init__(**kwargs)
        self.arg = arg

    async def run(self):
        print(f"[pid:{self.pid}] Hello async:", self.arg, self)
        processes = []
        if self.arg < 10:
            await asyncio.sleep(0.3)
            processes.append(MyProcess(self.arg + 1, scope=self.scope).launch())
        await asyncio.gather(*processes)
        print(f"[pid:{self.pid}] Goodbye async:", self.arg, self)


async def main():
    def create_worker(i):
        worker = lsys.create_worker(f"main-{i}")
        return lsys.create_scope(worker)

    workers = [create_worker(i) for i in range(3)]
    processes = []
    for i in range(10):
        processes.append(MyProcess(i, scope=workers[i % len(workers)]).launch())
        processes.append(MyProcess(i * 100, scope=workers[i % len(workers)]).launch())
        processes.append(MyProcess(i * 1000, scope=workers[i % len(workers)]).launch())
        await asyncio.sleep(0.1)

    print("<<MAIN WAITING>>")
    await asyncio.gather(*processes)
    print("** MAIN DONE **")
    return i


print("RESULT:", lsys.run(main()))
