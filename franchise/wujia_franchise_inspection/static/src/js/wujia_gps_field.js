/** @odoo-module **/

import { Component, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class WujiaGpsField extends Component {
    static template = xml`
        <div class="wujia-gps-field-container d-flex flex-wrap align-items-center gap-2 py-1">
            <t t-if="hasCoordinates">
                <div class="d-flex align-items-center gap-2 p-2 rounded border bg-light shadow-sm">
                    <i class="fa fa-map-marker text-danger fa-lg" t-att-title="titleGpsLocation"></i>
                    <div>
                        <div class="fw-bold text-dark small">
                            <t t-esc="latitude.toFixed(6)"/>, <t t-esc="longitude.toFixed(6)"/>
                        </div>
                        <div class="text-muted" style="font-size: 11px;">
                            <t t-esc="props.record.data.checkin_address or ''"/>
                        </div>
                    </div>
                    <button type="button" 
                            class="btn btn-sm btn-outline-primary ms-2 d-flex align-items-center gap-1 shadow-sm"
                            t-on-click="openGoogleMaps" 
                            t-att-title="titleMapBtn">
                        <i class="fa fa-external-link"></i>
                        <span t-esc="labelViewMap"/>
                    </button>
                </div>
            </t>
            <t t-else="">
                <div class="text-muted small fst-italic me-2 p-2 rounded border bg-light">
                    <i class="fa fa-map-marker text-secondary me-1"></i>
                    <span t-esc="labelNoGps"/>
                </div>
            </t>

            <button type="button" 
                    class="btn btn-sm btn-primary d-flex align-items-center gap-1 shadow-sm"
                    t-att-disabled="state.isLocating"
                    t-on-click="getCurrentLocation"
                    t-att-title="titleGetGpsBtn">
                <t t-if="state.isLocating">
                    <i class="fa fa-spinner fa-spin"></i>
                    <span t-esc="labelLocating"/>
                </t>
                <t t-else="">
                    <i class="fa fa-crosshairs"></i>
                    <span><t t-if="hasCoordinates" t-esc="labelUpdateGps"/><t t-else="" t-esc="labelGetGps"/></span>
                </t>
            </button>
        </div>
    `;

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({
            isLocating: false,
        });
    }

    get titleGpsLocation() {
        return _t("GPS Location");
    }

    get labelViewMap() {
        return _t("View on Google Maps");
    }

    get titleMapBtn() {
        return _t("Open location on Google Maps");
    }

    get labelNoGps() {
        return _t("No GPS coordinates recorded");
    }

    get titleGetGpsBtn() {
        return _t("Click to request permission and acquire GPS coordinates from browser/device");
    }

    get labelLocating() {
        return _t("Locating GPS...");
    }

    get labelUpdateGps() {
        return _t("Re-acquire GPS");
    }

    get labelGetGps() {
        return _t("Get Current Location (GPS)");
    }

    get latitude() {
        return this.props.record.data.latitude || 0;
    }

    get longitude() {
        return this.props.record.data.longitude || 0;
    }

    get hasCoordinates() {
        return Boolean(this.latitude || this.longitude);
    }

    get mapsUrl() {
        if (!this.hasCoordinates) return "";
        return `https://www.google.com/maps?q=${this.latitude},${this.longitude}`;
    }

    get isReadonly() {
        return this.props.readonly;
    }

    async getCurrentLocation() {
        if (!navigator.geolocation) {
            this.notification.add(
                _t("Your browser does not support Geolocation (GPS)!"),
                { type: "danger" }
            );
            return;
        }

        this.state.isLocating = true;

        const options = {
            enableHighAccuracy: true,
            timeout: 12000,
            maximumAge: 0,
        };

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const accuracy = Math.round(position.coords.accuracy || 0);

                const now = new Date();
                const timeStr = now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
                const infoText = `GPS: ${lat.toFixed(6)}, ${lng.toFixed(6)} (±${accuracy}m) at ${timeStr}`;

                try {
                    // 1. Update form record state
                    await this.props.record.update({
                        latitude: lat,
                        longitude: lng,
                        checkin_address: infoText,
                    });

                    // 2. Direct ORM backend persist if record exists
                    if (this.props.record.resId) {
                        try {
                            await this.orm.call("wujia.franchise.inspection", "action_update_gps_location", [
                                [this.props.record.resId],
                                lat,
                                lng,
                                infoText,
                            ]);
                        } catch (rpcErr) {
                            console.log("Direct ORM update:", rpcErr);
                        }
                    }

                    // 3. Save the form record
                    try {
                        await this.props.record.save();
                    } catch (saveErr) {
                        console.log("Record auto-save:", saveErr);
                    }

                    const successMsg = _t("GPS location acquired and saved successfully: %s, %s (Accuracy: ±%sm)", lat.toFixed(6), lng.toFixed(6), accuracy);
                    this.notification.add(successMsg, { type: "success" });
                } catch (error) {
                    console.error("Error updating GPS coordinates:", error);
                } finally {
                    this.state.isLocating = false;
                }
            },
            (error) => {
                this.state.isLocating = false;
                let errMsg = _t("Unable to acquire GPS location.");
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        errMsg = _t("You denied access to location. Please grant Location permission in your browser address bar!");
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errMsg = _t("Location information is currently unavailable. Please enable GPS and network connection!");
                        break;
                    case error.TIMEOUT:
                        errMsg = _t("GPS request timed out. Please try again!");
                        break;
                }
                this.notification.add(errMsg, { type: "warning" });
            },
            options
        );
    }

    openGoogleMaps() {
        if (!this.hasCoordinates) {
            this.notification.add(
                _t("No GPS coordinates to open Google Maps! Please click 'Get Current Location' first."),
                { type: "warning" }
            );
            return;
        }
        window.open(this.mapsUrl, "_blank", "noopener,noreferrer");
    }
}

export const wujiaGpsField = {
    component: WujiaGpsField,
    displayName: _t("GPS Location"),
    supportedTypes: ["char", "text"],
};

registry.category("fields").add("wujia_gps_field", wujiaGpsField);
