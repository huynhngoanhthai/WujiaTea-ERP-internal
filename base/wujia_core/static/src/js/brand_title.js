import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { titleService } from "@web/core/browser/title_service";

// Tab backend khi chưa có action (chỉ còn fallback "Odoo") ⇒ tên thương hiệu; có action giữ nguyên.
export const brandTitleService = {
    ...titleService,
    start(env, deps) {
        const title = titleService.start(env, deps);
        const brand = session.wj_brand_name;
        if (!brand) {
            return title;
        }
        const apply = () => {
            if (!Object.keys(title.getParts()).length && document.title.replace(/^\(\d+\) /, "") === "Odoo") {
                document.title = document.title.replace(/Odoo$/, brand);
            }
        };
        return {
            get current() {
                return document.title;
            },
            getParts: title.getParts,
            setCounters(counters) {
                title.setCounters(counters);
                apply();
            },
            setParts(parts) {
                title.setParts(parts);
                apply();
            },
        };
    },
};

registry.category("services").add("title", brandTitleService, { force: true });
