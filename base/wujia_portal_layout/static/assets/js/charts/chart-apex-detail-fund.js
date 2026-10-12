/*=========================================================================================
    File Name: chart-apex-detail-fund.js
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
    // Line Chart
    // ----------------------------------
    var lineChartOptions = {
        chart: {
            height: 350,
            type: 'line',
            zoom: {
                enabled: false
            },
            animations: {
                enabled: true,
                easing: 'easeinout',
                speed: 800,
                animateGradually: {
                    enabled: true,
                    delay: 150
                },
                dynamicAnimation: {
                    enabled: true,
                    speed: 350
                }
            }
        },
        colors: themeColors,
        dataLabels: {
            enabled: true
        },
        stroke: {
            curve: 'straight'
        },
        series: [{
            name: "Amount",
            data: data_interested,
        }],

        grid: {
            row: {
                colors: ['#f3f3f3', 'transparent'], // takes an array which will be repeated on columns
                opacity: 0.5
            },
        },
        xaxis: {
            categories: data_fund_month,
        },
        yaxis: {
            tickAmount: 5,
            opposite: yaxis_opposite
        }
    }
    var lineChart = new ApexCharts(
        document.querySelector("#line-chart-detail-investment-package"),
        lineChartOptions
    );
    lineChart.render();
});
