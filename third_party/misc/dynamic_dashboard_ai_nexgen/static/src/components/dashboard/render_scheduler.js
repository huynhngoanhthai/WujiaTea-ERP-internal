/** Copyright (C) NexGen Solutions */
/** @odoo-module **/

/**
 * Serializes heavy AmCharts work so the browser stays interactive
 * (scroll / clicks) while a dashboard with many cards boots.
 */

const MAX_CONCURRENT = 1;
const queue = [];
let active = 0;
let paintBurstUntil = 0;

/** Mark a boot/refresh window where animations should stay off. */
export function markDashboardPaintBurst(ms = 5000) {
    paintBurstUntil = Math.max(paintBurstUntil, Date.now() + ms);
}

export function isDashboardPaintBurst() {
    return Date.now() < paintBurstUntil;
}

export function yieldToBrowser() {
    return new Promise((resolve) => {
        if (typeof requestIdleCallback === "function") {
            requestIdleCallback(() => resolve(), { timeout: 64 });
        } else {
            requestAnimationFrame(() => setTimeout(resolve, 0));
        }
    });
}

/**
 * Schedule a chart/map build. Returns a cancel function.
 * Only one chart builds at a time; each job waits for an idle slot.
 */
export function scheduleChartRender(task) {
    let cancelled = false;
    const job = {
        task,
        isCancelled: () => cancelled,
    };
    queue.push(job);
    _pump();
    return () => {
        cancelled = true;
    };
}

function _pump() {
    if (active >= MAX_CONCURRENT) {
        return;
    }
    // Drop cancelled jobs at the head
    while (queue.length && queue[0].isCancelled()) {
        queue.shift();
    }
    if (!queue.length) {
        return;
    }

    const job = queue.shift();
    active += 1;

    const run = async () => {
        try {
            if (!job.isCancelled()) {
                await job.task();
            }
        } catch (e) {
            console.warn("Scheduled chart render failed", e);
        } finally {
            active -= 1;
            await yieldToBrowser();
            _pump();
        }
    };

    if (typeof requestIdleCallback === "function") {
        requestIdleCallback(() => {
            run();
        }, { timeout: 100 });
    } else {
        setTimeout(run, 0);
    }
}
