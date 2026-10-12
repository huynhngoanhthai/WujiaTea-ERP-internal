$(document).ready(function () {
    // $("#reply").click(function () {
    //     $("#replyticket").slideToggle();
    // });
    //
    // $('.conversion_update').click(function (e) {
    //     console.log(this, e);
    //     let state = $(this).data('state');
    //     let csrf_token = $('input[name="csrf_token"]').attr('value');
    //     $.ajax({
    //         method: 'PUT',
    //         url: location.href,
    //         data: {state, csrf_token},
    //         success: function (text) {
    //             try {
    //                 let data = JSON.parse(text)
    //                 if (data.success) {
    //                     location.reload();
    //                 } else {
    //                     // todo display message
    //                 }
    //             } catch (e) {
    //             }
    //         }
    //     })
    // });
    // document.querySelectorAll('.currency').forEach(v => $(v).text(Math.floor(parseFloat($(v).text()) * 100) / 100));
    //
    //
    // $("#Subscribed").click(function () {
    //     return renderItems("Subscribed");
    // });
    //
    // $("#Unsubscribed").click(function () {
    //     return renderItems("Unsubscribed");
    // });
    //
    //
    //
    // function renderItem(person) {
    //     var invest = '';
    //     if (person.invest) {
    //         let invest_text = new Intl.NumberFormat('en-US', {
    //             style: 'currency',
    //             currency: 'USD'
    //         }).format(person.invest);
    //         invest = `<span>${invest_text}</span>`;
    //     }
    //     var rank = person.rank ? `<span class="level_rank">${person.rank}</span>` : '';
    //     return `<div class="col-3">
    //             <div class="orgchart_person1" style="float: left">
    //             <img class="avatar img-thumbnail"
    //                  src="/profile/avatar/${person.id}"/>
    //             <div class="person_info">
    //                 <div class="name">${person.name}</div>
    //                 <div class="email">${person.email}</div>
    //                 <div class="level">
    //                     ${rank}
    //                     ${invest}
    //                 </div>
    //             </div>
    //         </div>
    //         </div>`
    // }
    //
    // var items = [];
    //
    // function renderItems(type) {
    //     var data_arr = [];
    //     data_arr.push(data);
    //     if (data.children) {
    //         data.children.forEach((d) => {
    //             data_arr.push(d)
    //             if (d.children) {
    //                 d.children.forEach((c) => {
    //                     data_arr.push(c)
    //                 })
    //             }
    //         })
    //     }
    //
    //     if (type == "Unsubscribed") {
    //         items = data_arr.filter(value => parseFloat(value.invest) > 0);
    //     } else {
    //         items = data_arr.filter(value => parseFloat(value.invest) > 0);
    //     }
    //     var render_html = items.map(v => renderItem(v));
    //
    //     if (items.length) {
    //         $('#network_data_array').html(render_html);
    //         $('#network_data_array').removeClass('hidden');
    //         $('#chart-container').addClass('hidden');
    //         $('#network_search').removeClass('hidden').val('');
    //     }
    // }
    //
    // $('#network_search').keyup(function () {
    //     if ($(this).val().trim().length) {
    //         var items_search = items.filter(v => {
    //             let regex = new RegExp($(this).val(), 'g');
    //
    //             return regex.test(v.name) || regex.test(v.rank) || regex.test(v.email);
    //         });
    //     } else {
    //         console.log("hello");
    //     }
    //
    //     var render_search = items_search.map(v => renderItem(v));
    //     $('#network_data_array').html(render_search);
    // });
    //
    // UI-PC-BASE-012: bộ dò active theo href này gắn .active cho MỌI thẻ <a> có href
    // trùng location.pathname → ở /portal nó sáng cả "Trang chủ" lẫn "Công nợ"
    // (href placeholder /portal) và gắn cả cho logo navbar. Sidebar portal giờ tính
    // active tại server trong pc_sidenav.xml, nên ở đây loại trừ #main-menu-navigation
    // và mọi thứ ngoài .main-menu. Giữ lại cho các menu bcore legacy.
    var path = location.pathname;
    const reg = /\/[^\/]+\/vi\/bcore/
    var path1 = path.replace(reg,'/bcore');
    // Sidebar portal (nhận diện bằng .wujia-nav-header) tự tính active tại server
    // ⇒ bỏ qua hoàn toàn, kể cả logo trong .navbar-header (href="/portal" nên ở
    // trang chủ nó cũng bị gắn .active). Menu bcore legacy vẫn dùng dò href như cũ.
    var isWujiaSidenav = !!document.querySelector('#main-menu-navigation .wujia-nav-header');
    if (!isWujiaSidenav) {
        document.querySelectorAll('a[href="' + path1 + '"]').forEach((el) => {
            $(el).parent('li').parents('li').addClass('open');
            $(el).parent('li').addClass('active');
        });
    }
    
    // $('#amount').keyup(function () {
    //     document.getElementById('fee').value = Math.floor(parseFloat($(this).val() * 1.5/100) * 100) / 100;
    //     document.getElementById('total').value = Math.floor((Math.floor(parseFloat($(this).val()) * 100) / 100 + Math.floor(parseFloat($(this).val() * 1.5/100) * 100) / 100) * 100) / 100;
    // })
    //
    // $("#withdraw_all").click(function () {
    //     document.getElementById('total').value = parseFloat($('#tientrongvi').text());
    //     document.getElementById('fee').value = Math.floor(parseFloat($('#tientrongvi').text() / 101.5 * 1.5) * 100) / 100;
    //     document.getElementById('amount').value = Math.floor((parseFloat($('#tientrongvi').text()) - Math.floor(parseFloat($('#tientrongvi').text() / 101.5 * 1.5) * 100) / 100) * 100)/100;
    // });
    //
    // if(type == 1){
    //     return renderItems("Subscribed");
    // }
    // if(type == 2){
    //     return renderItems("Unsubscribed");
    // }
});

