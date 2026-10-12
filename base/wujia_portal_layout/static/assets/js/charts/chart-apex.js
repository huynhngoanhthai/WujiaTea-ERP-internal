/*=========================================================================================
    File Name: chart-apex.js
    Description: Apexchart Examples
    ----------------------------------------------------------------------------------------
    Item Name: Vuexy  - Vuejs, HTML & Laravel Admin Dashboard Template
    Author: PIXINVENT
    Author URL: http://www.themeforest.net/user/pixinvent
==========================================================================================*/

$(document).ready(function () {

    var $primary = '#0776be',
        $success = '#B32F1C',
        $danger = '#0E623B',
        $warning = '#0E623B',
        $info = '#0E623B',
        $label_color_light = '#dae1e7';

    var themeColors = [$primary, $warning, $success, $danger, $info];

    // RTL Support
    var yaxis_opposite = false;
    if ($('html').data('textdirection') == 'rtl') {
        yaxis_opposite = true;
    }

// Column Chart
    // ----------------------------------
    var data_fund_management = $("#column-chart-value").val()
    console.log('hello may cung = ', data_fund_management)

    var columnChartOptions = {
        chart: {
            height: 350,
            type: 'bar',
        },
        colors: themeColors,
        plotOptions: {
            bar: {
                horizontal: false,
                endingShape: 'rounded',
                columnWidth: '55%',
            },
        },
        dataLabels: {
            enabled: true
        },
        stroke: {
            show: true,
            width: 2,
            colors: ['transparent']
        },
        series: [{
            name: _t('Net Profit'),
            data: data1
        }, {
            name: _t('Revenue'),
            data: data2
        }],
        legend: {
            offsetY: -10
        },
        xaxis: {
            categories: data_month,
        },
        yaxis: {
            title: {
                text: 'USD (thousands)'
            },
            opposite: yaxis_opposite
        },
        fill: {
            opacity: 1

        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return "$ " + val + " thousands"
                }
            }
        }
    }
    var columnChart = new ApexCharts(
        document.querySelector("#column-chart"),
        columnChartOptions
    );
    columnChart.render();

});
