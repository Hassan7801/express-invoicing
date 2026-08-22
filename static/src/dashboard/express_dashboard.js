import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { formatMonetary, formatFloat } from "@web/views/fields/formatters";

export class ExpressDashboard extends Component {
    static template = "express_invoicing.Dashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartRef = useRef("chart");
        this.chart = null;
        this.state = useState({
            period: "today",
            loading: true,
            data: {},
        });
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadData();
        });
        useEffect(
            () => {
                this.renderChart();
            },
            () => [this.state.loading, this.state.data]
        );
        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    get periods() {
        return [
            { id: "today", label: _t("Today") },
            { id: "week", label: _t("This week") },
            { id: "month", label: _t("This month") },
        ];
    }

    async setPeriod(period) {
        if (this.state.period === period) {
            return;
        }
        this.state.period = period;
        await this.loadData();
    }

    async loadData() {
        this.state.loading = true;
        this.state.data = await this.orm.call("account.move", "get_express_dashboard_data", [
            this.state.period,
        ]);
        this.state.loading = false;
    }

    formatMoney(value) {
        return formatMonetary(value || 0, { currencyId: this.state.data.currency_id });
    }

    formatQty(value) {
        return formatFloat(value || 0, { digits: [16, 2] });
    }

    async openAction(key) {
        const action = this.state.data.actions && this.state.data.actions[key];
        if (!action) {
            return;
        }
        await this.action.doAction(action);
    }

    openProduct(productId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: productId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    renderChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        if (!this.chartRef.el || this.state.loading) {
            return;
        }
        const rows = this.state.data.top_qty || [];
        this.chart = new Chart(this.chartRef.el, {
            type: "bar",
            data: {
                labels: rows.map((row) => row.name),
                datasets: [
                    {
                        label: _t("Quantity"),
                        data: rows.map((row) => row.qty),
                        backgroundColor: "#714B67",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: { beginAtZero: true },
                },
            },
        });
    }
}

registry.category("actions").add("express_invoicing.dashboard", ExpressDashboard);
