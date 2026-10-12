$(function () {
    var datascource = data_chart;

    var nodeTemplate = function (data) {
        let content = '';
        let email = '';

        if (data.email) {
            email += `<div class="email">${data.email}</div>`
        }
        if (data.tag) {
            content += `<span class="">${data.tag}</span></br><span class="">$ ${data.amount}</span>`;
        }
        if (content.length) {
            content = `<div class="level">${content}</div>`
        }
        return `
            <div class="orgchart_person">
                <img class="avatar img-thumbnail" src="/profile/avatar/${data.id}"/>
                <div class="person_info">
                    <div class="name">${data.name}</div>
                    ${email}
                    ${content}
                </div>
            </div>`;
    };

    $('#chart-network').orgchart({
        data: datascource,
        verticalLevel: 2,
        visibleLevel: 3,
        'nodeTemplate': nodeTemplate
    });

});