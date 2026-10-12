import { Component, xml } from "@odoo/owl";
import { Select } from "@web/core/tree_editor/tree_editor_components";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";


export class KsDropDown extends Select{
    setup(){
        super.setup();
        this.activeOption = this.props.options[0][1] || "Select"
    }

    deserialize(value, activeOption = false){
        if(activeOption)
            this.activeOption = activeOption
        return JSON.parse(value);
    }
}

KsDropDown.template = xml`<Dropdown menuClass="'o_input pe-3 text-truncate'">
                                <button class="text-decoration-none" href="#" role="button" aria-expanded="false">
                                    <t t-out="activeOption"/>
                                </button>
                                <t t-set-slot="content">
                                    <DropdownItem
                                        t-foreach="props.options"
                                        t-as="option"
                                        t-key="serialize(option[0])"
                                        class="{ '': true }"
                                        t-esc="option[1]"
                                        onSelected="() => this.props.update(this.deserialize(serialize(option[0]), option[1]))"
                                      />
                                </t>
                            </Dropdown>`

KsDropDown.components = { Dropdown, DropdownItem }


