/*=========================================================================================
    File Name: chart-apex-overview.js
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
            name: 'Turnover',
            data: data_turnover
        }],
        legend: {
            offsetY: -10
        },
        xaxis: {
            categories: data_member,
        },
        yaxis: {
            title: {
                text: 'USD ($)'
            },
            opposite: yaxis_opposite
        },
        fill: {
            opacity: 1
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return "$ " + val
                }
            }
        }
    }
    var columnChart = new ApexCharts(
        document.querySelector("#column-chart-overview"),
        columnChartOptions
    );
    columnChart.render();

});
