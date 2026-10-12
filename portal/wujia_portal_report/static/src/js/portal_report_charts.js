/* Báo cáo — chart bằng ApexCharts (đã load sẵn ở wujia_portal_layout/assets).
 *
 * Quy ước BA (STT12 #4): chiều cao cột = DOANH THU, số in trên/trong cột = SỐ ĐƠN.
 * Vì vậy chỉ còn 1 series cột; số đơn đi vào dataLabels chứ không thành series thứ 2
 * (series đường cũ làm hai đơn vị đo chung một khung, đọc sai tỷ lệ tiền).
 *
 * Payload JSON đọc từ data-chart-payload → 1 init/chart, KHÔNG thêm AJAX.
 * Chart nằm trong vùng swap của wj_ajax_list → vẽ lại sau mỗi lần lọc, nếu không
 * ApexCharts đã render vào node cũ (đã bị thay) và biểu đồ biến mất.
 */
(function () {
    "use strict";

    var charts = [];

    function wujiaColor(name, fallback) {
        var v = getComputedStyle(document.documentElement)
            .getPropertyValue("--wujia-" + name).trim();
        return v || fallback;
    }

    function msg(node, key, fallback, arg) {
        var text = window.wjMsg ? window.wjMsg(node, key, fallback) : fallback;
        return arg === undefined ? text : text.replace("%s", arg);
    }

    function orderCount(node, c) {
        return c === 1 ? msg(node, "order", "%s order", c) : msg(node, "orders", "%s orders", c);
    }

    /* 2.800.000 → "2,8tr" · 700.000 → "700k" ở vi_VN; đơn vị + dấu thập phân theo ngôn ngữ người xem. */
    function shortMoney(node, payload, v) {
        var n = Number(v) || 0;
        if (Math.abs(n) >= 1e6) {
            var m = String(Math.round(n / 1e5) / 10).replace(".", payload.decimal_point || ".");
            return msg(node, "million", "%sM", m);
        }
        if (Math.abs(n) >= 1e3) {
            return msg(node, "thousand", "%sK", Math.round(n / 1e3));
        }
        return String(Math.round(n));
    }

    function fullMoney(v) {
        return Number(v || 0).toLocaleString(document.documentElement.lang || undefined);
    }

    function monthsOptions(payload, mobile, node) {
        var primary = wujiaColor("primary", "#28A9DF");
        /* 8 tháng "07/2026" không đủ chỗ trong 334px của mobile: để nguyên thì
           ApexCharts cắt thành "07/2…", ép trim:false thì các nhãn chồng lên nhau.
           Mobile rút thành "07/26", tooltip vẫn trả về nhãn đầy đủ. */
        var full = payload.months_label || [];
        var months = mobile
            ? full.map(function (l) { return l.replace(/\/\d{2}(\d{2})$/, "/$1"); })
            : full;
        /* yaxis.title chỉ được TỒN TẠI ở bản PC. Truyền title: undefined làm
           ApexCharts đọc title.text của undefined → ném lỗi và chart mobile
           không vẽ ra gì (canvas rỗng), nên phải bỏ hẳn khoá. */
        var yaxis = {
            labels: {
                formatter: function (v) { return shortMoney(node, payload, v); },
                style: { fontSize: mobile ? "11px" : "12px" },
            },
        };
        if (!mobile) {
            /* Ký hiệu tiền lấy từ payload (currency công ty), không gõ 'đ' cứng. */
            yaxis.title = {
                text: msg(node, "revenue", "Revenue") + (payload.currency ? " (" + payload.currency + ")" : ""),
                style: { fontWeight: 500 },
            };
        }
        return {
            chart: {
                type: "bar",
                height: mobile ? 180 : 250,
                toolbar: { show: false },
                fontFamily: "inherit",
                parentHeightOffset: 0,
            },
            series: [{ name: msg(node, "revenue", "Revenue"), data: payload.months_total || [] }],
            colors: [primary],
            plotOptions: {
                bar: {
                    columnWidth: mobile ? "45%" : "38%",
                    borderRadius: 4,
                    /* Mockup đặt số đơn NẰM TRONG cột, sát mép trên (cách ~9px). */
                    dataLabels: { position: "top" },
                },
            },
            /* Nhãn = SỐ ĐƠN. Cột thấp thì Apex tự đẩy nhãn ra ngoài đỉnh cột
               (dataLabels.position + offset), tỷ lệ tiền của cột không đổi. */
            dataLabels: {
                enabled: true,
                formatter: function (val, opt) {
                    var counts = payload.months_count || [];
                    return counts[opt.dataPointIndex] != null
                        ? String(counts[opt.dataPointIndex]) : "";
                },
                offsetY: 16,
                /* Mockup vẽ chữ trắng trong cột, nhưng cột thấp (tháng ít doanh thu)
                   đẩy nhãn ra nền trắng → mất chữ. Bản ApexCharts đang bundle cũng
                   KHÔNG nhận hàm cho style.colors (ném lỗi, chart không vẽ), nên
                   dùng một màu tối duy nhất: đọc được cả trong cột lẫn trên nền. */
                style: {
                    fontSize: "12px",
                    fontWeight: 700,
                    colors: [wujiaColor("text-primary", "#111827")],
                },
            },
            xaxis: {
                categories: months,
                axisBorder: { show: false },
                axisTicks: { show: false },
                labels: {
                    rotate: 0,
                    hideOverlappingLabels: true,
                    trim: false,
                    style: { fontSize: mobile ? "9px" : "12px" },
                },
            },
            yaxis: yaxis,
            grid: { borderColor: wujiaColor("border-soft", "#EEF2F5"), strokeDashArray: 0 },
            legend: { show: false },
            tooltip: {
                x: {
                    formatter: function (v, opt) {
                        return (opt && full[opt.dataPointIndex]) || v;
                    },
                },
                y: {
                    formatter: function (v, opt) {
                        var counts = payload.months_count || [];
                        var c = counts[opt.dataPointIndex];
                        return fullMoney(v) + (c != null ? " · " + orderCount(node, c) : "");
                    },
                },
            },
        };
    }

    function stateOptions(payload, node) {
        return {
            chart: { type: "donut", height: 200, fontFamily: "inherit" },
            series: payload.state_count || [],
            labels: payload.state_label || [],
            colors: payload.state_color || [],
            legend: { show: false },
            dataLabels: { enabled: false },
            stroke: { width: 0 },
            plotOptions: {
                pie: {
                    donut: {
                        size: "70%",
                        labels: {
                            show: true,
                            value: { fontSize: "26px", fontWeight: 700, offsetY: 2 },
                            total: {
                                show: true,
                                label: msg(node, "total", "Total"),
                                fontSize: "13px",
                                formatter: function (w) {
                                    return w.globals.seriesTotals.reduce(function (a, b) {
                                        return a + b;
                                    }, 0);
                                },
                            },
                        },
                    },
                },
            },
            tooltip: { y: { formatter: function (v) { return orderCount(node, v); } } },
        };
    }

    function readPayload(node) {
        try {
            return JSON.parse(node.dataset.chartPayload || "{}");
        } catch (e) {
            console.warn("[portal_report] Cannot parse chart payload", e);
            return null;
        }
    }

    function renderInto(node, options) {
        var chart = new ApexCharts(node, options);
        charts.push(chart);
        chart.render();
    }

    function emptyNote(node) {
        var p = document.createElement("p");
        p.className = "wj-rep-chart-empty";
        p.textContent = msg(node, "no-data", "No data in the selected range.");
        node.replaceChildren(p);
    }

    function render() {
        while (charts.length) {
            charts.pop().destroy();
        }
        if (typeof ApexCharts === "undefined") {
            return;
        }

        /* Cả 2 bố cục cùng trong DOM (một cái display:none) — chỉ vẽ cái đang hiện,
           Apex đo sai kích thước khi container bị ẩn. */
        [
            { id: "report-chart-months", mobile: false },
            { id: "report-chart-months-m", mobile: true },
        ].forEach(function (spec) {
            var node = document.getElementById(spec.id);
            if (!node || !node.offsetParent) {
                return;
            }
            var payload = readPayload(node);
            if (!payload) {
                return;
            }
            if (payload.months_label && payload.months_label.length) {
                renderInto(node, monthsOptions(payload, spec.mobile, node));
            } else {
                emptyNote(node);
            }
        });

        var stateNode = document.getElementById("report-chart-state");
        if (stateNode && stateNode.offsetParent) {
            var pcNode = document.getElementById("report-chart-months");
            var payload = pcNode ? readPayload(pcNode) : null;
            if (payload && payload.state_label && payload.state_label.length) {
                renderInto(stateNode, stateOptions(payload, stateNode));
            } else {
                emptyNote(stateNode);
            }
        }
    }

    document.addEventListener("DOMContentLoaded", render);
    document.addEventListener("wj:list:swapped", render);
    /* Đổi bề rộng qua mốc 992 → bố cục kia lên sóng, chart của nó chưa từng vẽ. */
    window.addEventListener("resize", function () {
        clearTimeout(render._t);
        render._t = setTimeout(render, 200);
    });
})();
