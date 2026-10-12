/*=========================================================================================
    File Name: chart-apex.js
    Description: Apexchart Examples
    ----------------------------------------------------------------------------------------
    Item Name: Vuexy  - Vuejs, HTML & Laravel Admin Dashboard Template
    Author: PIXINVENT
    Author URL: http://www.themeforest.net/user/pixinvent
==========================================================================================*/
$(document).ready(function () {
    var $primary = '#14242A',
        $success = '#14242A',
        $danger = '#0E623B',
        $warning = '#B32F1C',
        $info = '#00cfe8'
    
    var themeColors = [$primary, $success, $danger, $warning, $info];
    var arrayMonth = ['T0', 'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11', 'T12']


    $("#form-register-investment").on("click", "#investment_packages_id", function () {

        var price_unit = $("#price_unit").val();
        if (price_unit == "") {
            var register_investment_id = $(this).attr('data-register_investment_id')
            var interest_rate = $(this).attr('data-interest_rate')
            var get_interest_rate = parseFloat(interest_rate) / 100
            var month = $(this).attr('data-month')
            month = month.split("_months", 1);
            var get_month = parseInt(month)
            console.log(register_investment_id, get_interest_rate, get_month)

            $('#investment_packages_id.interest_rate').removeClass('active')
            $('#investment_packages_id .card .card-body').removeClass('border-custom-primary')
            // Adding class to clicked list element
            $(this).addClass('active');
            if ($(this).hasClass('active')) {
                $("#investment_packages_id.active .card .card-body").addClass("border-custom-primary")
            }
            $("#collapseExample").addClass("hidden");
            ArrayNewinvestment_packages = new Array()
            arrayInfoinvestment_packages = [register_investment_id, get_interest_rate, get_month]
        } else {
            var register_investment_id = $(this).attr('data-register_investment_id')
            var interest_rate = $(this).attr('data-interest_rate')
            var get_interest_rate = parseFloat(interest_rate) / 100
            var month = $(this).attr('data-month')
            month = month.split("_months", 1);
            var get_month = parseInt(month)


            $('#investment_packages_id.interest_rate').removeClass('active')
            $('#investment_packages_id .card .card-body').removeClass('border-custom-primary')
            // Adding class to clicked list element
            $(this).addClass('active');
            if ($(this).hasClass('active')) {
                $("#investment_packages_id.active .card .card-body").addClass("border-custom-primary")
            }
            $("#collapseExample").addClass("hidden");
            ArrayNewinvestment_packages = new Array()
            arrayInfoinvestment_packages = [register_investment_id, get_interest_rate, get_month]
            var arrayMonthIndex = new Array()
            var arrayAmount = new Array()

            total = 0;

            for (i = 0; i <= arrayInfoinvestment_packages[2]; i++) {
                total = parseFloat(price_unit) + (parseFloat(price_unit) * arrayInfoinvestment_packages[1]) * i
                arrayMonthIndex.push(arrayMonth[i])
                arrayAmount.push(total)
            }

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
                    curve: 'straight',
                    width: 3
                },
                series: [{
                    name: "Total",
                    data: arrayAmount,
                }],
                title: {
                    text: _t('Overview investment package'),
                    align: 'left'
                },
                grid: {
                    row: {
                        colors: ['#f3f3f3', 'transparent'], // takes an array which will be repeated on columns
                        opacity: 0.5
                    },
                },
                xaxis: {
                    categories: arrayMonthIndex,
                },
                yaxis: {
                    tickAmount: 5,
                    opposite: yaxis_opposite
                }
            }
            var lineChart = new ApexCharts(
                document.querySelector("#line-chart"),
                lineChartOptions
            );
            lineChart.render();
            lineChart.resetSeries();
        }

    })
    $("#price_unit").keyup(function () {
        // RTL Support
        $("#collapseExample").addClass("hidden");
        var price_unit = $("#price_unit").val();
        price_unit = parseFloat(price_unit)
        let current_balance = $("#current_balance").attr('data-current_balance')
        current_balance = parseFloat(current_balance)
        console.log(price_unit, current_balance)
        var arrayMonthIndex = new Array()
        var arrayAmount = new Array()

        if (price_unit <= current_balance && price_unit >= 15000) {
            $("#line-chart").removeClass('hidden');
            total = 0;
            for (i = 0; i <= arrayInfoinvestment_packages[2]; i++) {
                total = parseFloat(price_unit) + (parseFloat(price_unit) * arrayInfoinvestment_packages[1]) * i
                arrayMonthIndex.push(arrayMonth[i])
                arrayAmount.push(total)
            }

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
                    }
                },
                colors: themeColors,
                dataLabels: {
                    enabled: true
                },
                stroke: {
                    curve: 'straight',
                    width: 3
                },
                series: [{
                    name: "Desktops",
                    data: arrayAmount,
                }],
                title: {
                    text: _t('Overview investment package'),
                    align: 'left'
                },
                grid: {
                    row: {
                        colors: ['#f3f3f3', 'transparent'], // takes an array which will be repeated on columns
                        opacity: 0.5
                    },
                },
                xaxis: {
                    categories: arrayMonthIndex,
                },
                yaxis: {
                    tickAmount: 5,
                    opposite: yaxis_opposite
                }
            }
            var lineChart = new ApexCharts(
                document.querySelector("#line-chart"),
                lineChartOptions
            );
            lineChart.render();
            lineChart.resetSeries();
        } else {
            $("#line-chart").addClass('hidden')
        }
    })

});