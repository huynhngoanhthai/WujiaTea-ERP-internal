/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { Component,useRef } from "@odoo/owl";

export class Ksiconselectordialog extends Component {
    setup() {
    this.ks_modal = useRef("ks_modal")
    this.ks_search = useRef("ks_search")
    this.ksSelectedIcon = false
    }

    ks_icon_container_list(e){
        var self = this;
        (this.ks_modal.el.querySelectorAll('.ks_icon_container_list')).forEach((selected_icon) => {
            selected_icon.classList.remove('ks_icon_selected');
        });
        e.currentTarget.classList.add('ks_icon_selected');
        const openButton = document.querySelector(".ks_icon_container_open_button");
        if (openButton) {
            openButton.classList.remove("d-none");
        }
        const selectedSpan = e.currentTarget.querySelector('span');
        if (selectedSpan) {
            self.ksSelectedIcon = selectedSpan.getAttribute('id').split('.')[1];
        }
    }

     ks_fa_icon_search(e) {
        var self = this
        if(this.ks_search.el.querySelectorAll('.ks_fa_search_icon').length > 0){
            this.ks_search.el.querySelectorAll('.ks_fa_search_icon').forEach(function(el){
                el.remove();
            })
        }
        var ks_fa_icon_name = this.ks_search.el.querySelectorAll('.ks_modal_icon_input')[0].value;
        if (ks_fa_icon_name.slice(0, 3) === "fa-") {
            ks_fa_icon_name = ks_fa_icon_name.slice(3)
        }
        var ks_fa_icon_render = document.createElement('div');
        ks_fa_icon_render.classList.add('ks_icon_container_list', 'ks_fa_search_icon');

        var spanElement = document.createElement('span');
        spanElement.setAttribute('id', 'ks.' + ks_fa_icon_name.toLowerCase());
        spanElement.classList.add("fa", "fa-" + ks_fa_icon_name.toLowerCase(), "fa-4x");

        ks_fa_icon_render.appendChild(spanElement);

        this.ks_modal.el.appendChild(ks_fa_icon_render);

        this.ks_modal.el.querySelectorAll('.ks_fa_search_icon').forEach((item) => {
            item.addEventListener('click', this.ks_icon_container_list.bind(this));
        });
     }


    async _ks_icon_container_open_button(e){
        try {
            await this.props.confirm(this.ksSelectedIcon);
        } catch (e) {
            this.props.close();
        }
        this.props.close();
    }
}
Ksiconselectordialog.template = "Ksicondialog";
Ksiconselectordialog.props = {
    close: Function,
    confirm: { type: Function, optional: true },
    ks_icon_set: { type: Object, optional: true },
}
Ksiconselectordialog.components = { Dialog };
