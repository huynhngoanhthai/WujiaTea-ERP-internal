/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

export class WujiaInspectionChart extends Component {
  static template = xml`
        <div class="wujia-inspection-chart-container w-100 p-4 bg-white rounded border shadow-sm my-2" style="width: 100% !important; max-width: 100% !important;">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0 fw-bold text-primary fs-5">
                    <i class="fa fa-bar-chart me-2"></i> <t t-esc="chartTitle"/>
                </h6>
                <t t-if="chartData.hasData">
                    <div class="d-flex align-items-center gap-3">
                        <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-3 py-2 fs-6">
                            <i class="fa fa-square me-1" style="color: #28A9DF;"></i> <t t-esc="singleScoreLabel"/>
                        </span>
                        <span class="badge bg-warning-subtle text-warning border border-warning-subtle px-3 py-2 fs-6">
                            <i class="fa fa-minus me-1" style="color: #FF9F43; font-weight: bold;"></i> <t t-esc="avgScoreLabel"/> (<t t-esc="chartData.avgScore"/>)
                        </span>
                    </div>
                </t>
            </div>

            <t t-if="!chartData.hasData">
                <div class="alert alert-info d-flex align-items-center mb-0 py-4" role="alert">
                    <i class="fa fa-info-circle fa-2x me-3 text-info"></i>
                    <div>
                        <strong><t t-esc="noDataTitle"/></strong>
                        <div class="text-muted"><t t-esc="noDataDesc"/></div>
                    </div>
                </div>
            </t>

            <t t-else="">
                <div class="position-relative w-100" style="height: 350px; width: 100%;">
                    <svg t-att-viewBox="viewBox" style="width: 100%; height: 100%; display: block;" class="w-100 h-100">
                        <!-- Grid Lines -->
                        <t t-foreach="gridLines" t-as="grid" t-key="grid.val">
                            <line t-att-x1="padding.left" t-att-y1="grid.y" t-att-x2="chartWidth - padding.right" t-att-y2="grid.y" stroke="#edf2f7" stroke-width="1" stroke-dasharray="4,4" />
                            <text t-att-x="padding.left - 12" t-att-y="grid.y + 4" text-anchor="end" font-size="12" fill="#718096" font-weight="500"><t t-esc="grid.val"/></text>
                        </t>

                        <!-- Average Line -->
                        <line t-if="avgLineY !== false"
                              t-att-x1="padding.left" 
                              t-att-y1="avgLineY" 
                              t-att-x2="chartWidth - padding.right" 
                              t-att-y2="avgLineY" 
                              stroke="#FF9F43" 
                              stroke-width="2.5" 
                              stroke-dasharray="6,4" />

                        <!-- Bars -->
                        <t t-foreach="bars" t-as="bar" t-key="bar.idx">
                            <g class="wujia-chart-bar-group" style="cursor: pointer;">
                                <rect t-att-x="bar.x" 
                                      t-att-y="bar.y" 
                                      t-att-width="bar.width" 
                                      t-att-height="bar.height" 
                                      rx="6" 
                                      t-att-fill="bar.color" 
                                      t-att-stroke="bar.strokeColor" 
                                      stroke-width="1.5" />
                                
                                <text t-att-x="bar.x + bar.width / 2" 
                                      t-att-y="bar.y - 8" 
                                      text-anchor="middle" 
                                      font-size="13" 
                                      font-weight="bold" 
                                      t-att-fill="bar.textColor">
                                    <t t-esc="bar.displayScore"/>
                                </text>

                                <text t-att-x="bar.x + bar.width / 2" 
                                      t-att-y="chartHeight - padding.bottom + 22" 
                                      text-anchor="middle" 
                                      font-size="12" 
                                      font-weight="500"
                                      fill="#4A5568">
                                    <t t-esc="bar.date"/>
                                </text>
                            </g>
                        </t>
                    </svg>
                </div>
            </t>
        </div>
    `;

  get chartTitle() {
    return _t("Supervision Score History (Last 10 Rounds)");
  }

  get singleScoreLabel() {
    return _t("Score per Round");
  }

  get avgScoreLabel() {
    return _t("Average Score");
  }

  get noDataTitle() {
    return _t("No Historical Data Yet!");
  }

  get noDataDesc() {
    return (
      this.chartData.no_data_desc ||
      _t(
        "Please select a Supervision Template or this store has no completed/remediation inspection sheets yet.",
      )
    );
  }

  static props = {
    ...standardFieldProps,
  };

  get chartData() {
    const raw = this.props.record.data[this.props.name];
    if (!raw) return { hasData: false };
    try {
      const data = typeof raw === "string" ? JSON.parse(raw) : raw;
      const labels = data.labels || [];
      const scores = data.scores || [];
      const grades = data.grades || [];
      const displayScores = data.display_scores || [];
      const avgScores = data.avg_scores || [];
      const hasData = labels.length > 0 && scores.length > 0;
      const avgScore = avgScores.length > 0 ? avgScores[0] : 0;
      return { hasData, labels, scores, grades, displayScores, avgScores, avgScore };
    } catch (e) {
      return { hasData: false };
    }
  }

  get chartWidth() {
    return 1200;
  }
  get chartHeight() {
    return 320;
  }
  get padding() {
    return { top: 30, right: 35, bottom: 45, left: 50 };
  }
  get viewBox() {
    return "0 0 " + this.chartWidth + " " + this.chartHeight;
  }

  get gridLines() {
    const lines = [];
    const usableHeight =
      this.chartHeight - this.padding.top - this.padding.bottom;
    for (let val = 0; val <= 100; val += 20) {
      const y =
        this.chartHeight - this.padding.bottom - (val / 100) * usableHeight;
      lines.push({ val, y });
    }
    return lines;
  }

  get avgLineY() {
    const { avgScore, hasData } = this.chartData;
    if (!hasData) return false;
    const usableHeight =
      this.chartHeight - this.padding.top - this.padding.bottom;
    return (
      this.chartHeight -
      this.padding.bottom -
      (Math.min(Math.max(avgScore, 0), 100) / 100) * usableHeight
    );
  }

  get bars() {
    const { labels, scores, grades, displayScores, hasData } = this.chartData;
    if (!hasData) return [];
    const usableWidth =
      this.chartWidth - this.padding.left - this.padding.right;
    const usableHeight =
      this.chartHeight - this.padding.top - this.padding.bottom;
    const count = labels.length;
    const slotWidth = usableWidth / count;
    const barWidth = Math.min(Math.max(slotWidth * 0.45, 45), 85);

    return labels.map((date, idx) => {
      const score = scores[idx] || 0;
      const grade = grades[idx] || "";
      const displayScore = displayScores[idx] || (grade ? `${score} (${grade})` : `${score}`);
      const height = (Math.min(Math.max(score, 0), 100) / 100) * usableHeight;
      const x =
        this.padding.left + idx * slotWidth + (slotWidth - barWidth) / 2;
      const y = this.chartHeight - this.padding.bottom - height;

      // Dynamic colors based on Grade
      let color = "#28A9DF";
      let strokeColor = "#1B87B5";
      let textColor = "#1B87B5";

      if (grade === "A") {
        color = "#28C76F";
        strokeColor = "#1E9553";
        textColor = "#1E9553";
      } else if (grade === "B") {
        color = "#28A9DF";
        strokeColor = "#1B87B5";
        textColor = "#1B87B5";
      } else if (grade === "C") {
        color = "#FF9F43";
        strokeColor = "#D97B20";
        textColor = "#D97B20";
      } else if (grade === "D") {
        color = "#EA5455";
        strokeColor = "#BD2829";
        textColor = "#BD2829";
      }

      return {
        idx,
        date,
        score,
        grade,
        displayScore,
        color,
        strokeColor,
        textColor,
        x,
        y,
        width: barWidth,
        height,
      };
    });
  }
}

export const wujiaInspectionChartField = {
  component: WujiaInspectionChart,
  supportedTypes: ["text", "char"],
};

registry
  .category("fields")
  .add("wujia_inspection_chart", wujiaInspectionChartField);

import { DateTimeField, dateField } from "@web/views/fields/datetime/datetime_field";

export class WujiaMonthYearField extends DateTimeField {
  getFormattedValue(valueIndex) {
    const values = this.values;
    const value = values[valueIndex];
    if (!value) {
      return "";
    }
    return value.toFormat ? value.toFormat("MM/yyyy") : value;
  }
}

export function formatMonthYear(value) {
  if (!value) {
    return "";
  }
  return value.toFormat ? value.toFormat("MM/yyyy") : value;
}

export const wujiaMonthYearField = {
  ...dateField,
  component: WujiaMonthYearField,
  displayName: _t("Month / Year"),
  supportedTypes: ["date"],
  extractProps: (fieldInfo, dynamicInfo) => {
    const props = dateField.extractProps(fieldInfo, dynamicInfo);
    return {
      ...props,
      minPrecision: "months",
      maxPrecision: "months",
    };
  },
};

registry.category("formatters").add("wujia_month_year", formatMonthYear);
registry.category("fields").add("wujia_month_year", wujiaMonthYearField);
