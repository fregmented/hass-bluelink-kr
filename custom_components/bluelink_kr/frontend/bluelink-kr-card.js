const CARD_VERSION = "0.1.0";

/* global customElements */
const Lit = window.Lit || {};
const elementBase =
  customElements.get("ha-panel-lovelace") || customElements.get("hui-view");
const LitElementBase =
  Lit.LitElement ||
  window.LitElement ||
  (elementBase ? Object.getPrototypeOf(elementBase) : undefined);
const html =
  Lit.html ||
  window.html ||
  (LitElementBase ? LitElementBase.prototype?.html : undefined);
const css =
  Lit.css ||
  window.css ||
  (LitElementBase ? LitElementBase.prototype?.css : undefined);

if (!LitElementBase || !html || !css) {
  throw new Error("Hyundai Bluelink KR card: LitElement not found.");
}

class BluelinkKrCard extends LitElementBase {
  static get properties() {
    return {
      hass: {},
      _config: {},
    };
  }

  static getConfigElement() {
    return document.createElement("bluelink-kr-card-editor");
  }

  static getStubConfig(hass) {
    const sensorIds = Object.keys(hass?.states || {}).filter((eid) =>
      eid.startsWith("sensor.")
    );
    return {
      type: "custom:bluelink-kr-card",
      entities: {
        ev_soc: sensorIds[0] || "",
        driving_range: sensorIds[1] || "",
        odometer: sensorIds[2] || "",
      },
    };
  }

  setConfig(config) {
    if (!config?.entities || typeof config.entities !== "object") {
      throw new Error("The card requires an 'entities' object in the config.");
    }
    this._config = {
      title: config.title,
      show_warnings: config.show_warnings !== false,
      entities: config.entities,
    };
  }

  getCardSize() {
    return 3;
  }

  _entity(entityId) {
    if (!entityId || !this.hass?.states) {
      return undefined;
    }
    return this.hass.states[entityId];
  }

  _friendlyName(entity, fallback) {
    const name = entity?.attributes?.friendly_name || fallback || "";
    const suffixes = ["EV SOC", "Driving Range", "Odometer"];
    for (const suffix of suffixes) {
      if (name.toLowerCase().endsWith(suffix.toLowerCase())) {
        return name.slice(0, name.length - suffix.length).trim();
      }
    }
    return name || "Bluelink";
  }

  _deriveTitle(entities) {
    for (const entity of entities) {
      if (entity) {
        return this._friendlyName(entity);
      }
    }
    return "블루링크 차량";
  }

  _boolState(entity) {
    const raw = entity?.state;
    if (raw === undefined || raw === null) {
      return null;
    }
    const value = String(raw).toLowerCase();
    if (["on", "true", "1", "yes"].includes(value)) {
      return true;
    }
    if (["off", "false", "0", "no"].includes(value)) {
      return false;
    }
    return null;
  }

  _numericState(entity) {
    if (!entity) {
      return null;
    }
    const value = Number(entity.state);
    return Number.isNaN(value) ? null : value;
  }

  _formatValue(entity, fallback = "—") {
    if (!entity) {
      return fallback;
    }
    const state = entity.state;
    if (state === undefined || state === null) {
      return fallback;
    }
    if (["unknown", "unavailable"].includes(String(state).toLowerCase())) {
      return fallback;
    }
    const unit = entity.attributes?.unit_of_measurement;
    const numeric = Number(state);
    if (!Number.isNaN(numeric)) {
      const rounded =
        Math.abs(numeric) >= 100 ? Math.round(numeric) : numeric.toFixed(1);
      return unit ? `${rounded} ${unit}` : `${rounded}`;
    }
    return unit ? `${state} ${unit}` : `${state}`;
  }

  _chargingLabel(chargingEntity) {
    const state = this._boolState(chargingEntity);
    if (state === true) {
      return { label: "Charging", tone: "accent" };
    }
    if (state === false) {
      return { label: "Idle", tone: "muted" };
    }
    return { label: "Unknown", tone: "muted" };
  }

  _plugLabel(plugEntity) {
    const numeric = this._numericState(plugEntity);
    if (numeric === null) {
      return { label: "Plug unknown", tone: "muted" };
    }
    return numeric > 0
      ? { label: "Plugged", tone: "accent" }
      : { label: "Unplugged", tone: "warn" };
  }

  _timeLabel(remainEntity, estimateEntity) {
    const remainNumeric = this._numericState(remainEntity);
    const estimateNumeric = this._numericState(estimateEntity);
    const remainState =
      remainNumeric !== null && remainNumeric > 0
        ? this._formatValue(remainEntity)
        : null;
    const estimateState =
      estimateNumeric !== null && estimateNumeric > 0
        ? this._formatValue(estimateEntity)
        : null;
    return remainState || estimateState || "—";
  }

  _warningState(entity) {
    const boolState = this._boolState(entity);
    if (boolState === null) {
      return { active: false, label: "Unknown" };
    }
    return boolState
      ? { active: true, label: "Warning" }
      : { active: false, label: "OK" };
  }

  render() {
    if (!this._config || !this.hass) {
      return html``;
    }

    const entities = this._config.entities;
    const drivingRange = this._entity(entities.driving_range);
    const odometer = this._entity(entities.odometer);
    const evSoc = this._entity(entities.ev_soc);
    const chargingState = this._entity(entities.charging_state);
    const chargerConnection = this._entity(entities.charger_connection);
    const targetSoc = this._entity(entities.charging_target_soc);
    const remainTime = this._entity(entities.charging_time_remaining);
    const estimateTime = this._entity(entities.charging_time_estimate);
    const warnings = Array.isArray(entities.warnings)
      ? entities.warnings
          .map((id) => ({ id, entity: this._entity(id) }))
          .filter((item) => Boolean(item.entity))
      : [];

    const title =
      this._config.title ||
      this._deriveTitle([evSoc, drivingRange, odometer, chargingState]);
    const chargingLabel = this._chargingLabel(chargingState);
    const plugLabel = this._plugLabel(chargerConnection);
    const timeLabel = this._timeLabel(remainTime, estimateTime);

    return html`
      <ha-card>
        <div class="card__header">
          <div class="card__title">
            <div class="eyebrow">Hyundai Bluelink KR</div>
            <div class="title">${title}</div>
          </div>
          <div class="badge">v${CARD_VERSION}</div>
        </div>

        <div class="grid">
          <div class="stat">
            <div class="label">Driving Range</div>
            <div class="value">${this._formatValue(drivingRange)}</div>
            <div class="meta">
              ${drivingRange?.attributes?.timestamp || "—"}
            </div>
          </div>
          <div class="stat">
            <div class="label">Odometer</div>
            <div class="value">${this._formatValue(odometer)}</div>
            <div class="meta">
              ${odometer?.attributes?.timestamp || "—"}
            </div>
          </div>
          <div class="stat accent">
            <div class="label">EV SOC</div>
            <div class="value">${this._formatValue(evSoc)}</div>
            <div class="meta">
              ${evSoc?.attributes?.timestamp || "—"}
            </div>
          </div>
        </div>

        <div class="section">
          <div class="section__title">Charging</div>
          <div class="chips">
            <div class="chip ${chargingLabel.tone}">
              <span class="dot"></span>
              <span>${chargingLabel.label}</span>
            </div>
            <div class="chip ${plugLabel.tone}">
              <span class="dot"></span>
              <span>${plugLabel.label}</span>
            </div>
            <div class="chip">
              <span class="dot"></span>
              <span>Target ${this._formatValue(targetSoc)}</span>
            </div>
            <div class="chip">
              <span class="dot"></span>
              <span>Remaining ${timeLabel}</span>
            </div>
          </div>
        </div>

        ${this._config.show_warnings
          ? html`
              <div class="section">
                <div class="section__title">Warnings</div>
                ${warnings.length === 0
                  ? html`<div class="empty">Add warning entities to show them here.</div>`
                  : html`
                      <div class="warnings">
                        ${warnings.map(({ id, entity }) => {
                          const warningState = this._warningState(entity);
                          return html`
                            <div class="warning ${warningState.active ? "active" : ""}">
                              <div class="warning__name">
                                ${entity.attributes?.friendly_name || id}
                              </div>
                              <div class="warning__state">${warningState.label}</div>
                            </div>
                          `;
                        })}
                      </div>
                    `}
              </div>
            `
          : ""}
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      ha-card {
        background: linear-gradient(135deg, #0d1f33 0%, #081627 45%, #0c2f4e 100%);
        color: #e7f2ff;
        border: none;
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.35);
        padding: 18px;
      }

      .card__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
      }

      .card__title .eyebrow {
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #7bd8cb;
      }

      .card__title .title {
        font-size: 20px;
        font-weight: 700;
        margin-top: 2px;
      }

      .badge {
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 12px;
        color: #c7e5ff;
        background: rgba(255, 255, 255, 0.06);
      }

      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 12px;
        margin: 14px 0 4px;
      }

      .stat {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 12px 14px;
      }

      .stat.accent {
        border-color: rgba(91, 223, 210, 0.5);
        background: linear-gradient(
          135deg,
          rgba(91, 223, 210, 0.18),
          rgba(91, 140, 223, 0.08)
        );
      }

      .stat .label {
        font-size: 12px;
        color: #b7c6d8;
        letter-spacing: 0.02em;
      }

      .stat .value {
        font-size: 26px;
        font-weight: 700;
        margin-top: 4px;
      }

      .stat .meta {
        font-size: 11px;
        color: #8ea5be;
        margin-top: 4px;
      }

      .section {
        margin-top: 16px;
      }

      .section__title {
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #8bb4ff;
        margin-bottom: 8px;
      }

      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.1);
        font-size: 13px;
        color: #dfe9f6;
      }

      .chip .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.7);
      }

      .chip.accent {
        border-color: rgba(91, 223, 210, 0.7);
        box-shadow: 0 0 12px rgba(91, 223, 210, 0.4);
      }

      .chip.accent .dot {
        background: #5bded2;
      }

      .chip.warn {
        border-color: rgba(255, 188, 74, 0.8);
      }

      .chip.warn .dot {
        background: #ffbc4a;
      }

      .chip.muted {
        opacity: 0.8;
      }

      .warnings {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 8px;
      }

      .warning {
        padding: 10px 12px;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.07);
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #dfe9f6;
      }

      .warning.active {
        border-color: rgba(255, 111, 111, 0.5);
        background: linear-gradient(
          135deg,
          rgba(255, 111, 111, 0.2),
          rgba(255, 170, 91, 0.08)
        );
      }

      .warning__name {
        font-weight: 600;
        font-size: 13px;
      }

      .warning__state {
        font-size: 12px;
        color: rgba(255, 255, 255, 0.85);
      }

      .empty {
        color: #9db0c8;
        font-size: 13px;
        background: rgba(255, 255, 255, 0.04);
        border-radius: 10px;
        padding: 10px 12px;
        border: 1px dashed rgba(255, 255, 255, 0.1);
      }

      @media (max-width: 600px) {
        ha-card {
          padding: 14px;
        }

        .card__header {
          flex-direction: column;
          align-items: flex-start;
        }

        .grid {
          grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        }
      }
    `;
  }
}

customElements.define("bluelink-kr-card", BluelinkKrCard);

class BluelinkKrCardEditor extends LitElementBase {
  static get properties() {
    return {
      hass: {},
      _config: {},
    };
  }

  setConfig(config) {
    this._config = {
      show_warnings: true,
      ...config,
      entities: {
        ...(config?.entities || {}),
      },
    };
  }

  render() {
    if (!this.hass || !this._config) {
      return html``;
    }

    const entities = this._config.entities || {};
    const sensors = [
      { key: "ev_soc", label: "EV SOC 센서" },
      { key: "driving_range", label: "주행 가능 거리 센서" },
      { key: "odometer", label: "누적 주행거리 센서" },
      { key: "charging_state", label: "충전 상태 센서" },
      { key: "charger_connection", label: "충전 커넥터 연결 센서" },
      { key: "charging_target_soc", label: "목표 SOC 센서" },
      { key: "charging_time_remaining", label: "충전 남은 시간 센서" },
      { key: "charging_time_estimate", label: "충전 예상 시간 센서" },
    ];
    const warningRows = [...(entities.warnings || []), ""];

    return html`
      <div class="editor">
        <ha-textfield
          label="카드 제목 (선택)"
          .value=${this._config.title || ""}
          @input=${(ev) => this._onTitleChange(ev)}
        ></ha-textfield>

        <div class="row">
          <div class="row__label">경고 섹션 표시</div>
          <ha-switch
            .checked=${this._config.show_warnings !== false}
            @change=${(ev) => this._onWarningsToggle(ev)}
          ></ha-switch>
        </div>

        <div class="section">
          <div class="section__title">센서 매핑</div>
          ${sensors.map(
            (sensor) => html`
              <ha-entity-picker
                .hass=${this.hass}
                .value=${entities[sensor.key] || ""}
                .label=${sensor.label}
                .includeDomains=${["sensor"]}
                allow-custom-entity
                @value-changed=${(ev) =>
                  this._setEntity(sensor.key, ev.detail?.value)}
              ></ha-entity-picker>
            `
          )}
        </div>

        <div class="section">
          <div class="section__title">경고 센서 (선택)</div>
          <p class="hint">
            추가로 표시할 경고 센서를 선택하세요. 빈 항목을 선택하면 새 행이 추가됩니다.
          </p>
          ${warningRows.map(
            (id, idx) => html`
              <ha-entity-picker
                .hass=${this.hass}
                .value=${id}
                .label=${`경고 센서 ${idx + 1}`}
                .includeDomains=${["sensor"]}
                allow-custom-entity
                @value-changed=${(ev) => this._setWarning(idx, ev.detail?.value)}
              ></ha-entity-picker>
            `
          )}
        </div>
      </div>
    `;
  }

  _onTitleChange(ev) {
    const title = ev?.target?.value || "";
    const config = { ...this._config, title: title || undefined };
    this._updateConfig(config);
  }

  _onWarningsToggle(ev) {
    const checked = Boolean(ev?.target?.checked);
    const config = { ...this._config, show_warnings: checked };
    this._updateConfig(config);
  }

  _setEntity(key, value) {
    const entities = { ...(this._config?.entities || {}) };
    if (!value) {
      delete entities[key];
    } else {
      entities[key] = value;
    }
    this._updateConfig({ ...this._config, entities });
  }

  _setWarning(index, value) {
    const warnings = [...(this._config?.entities?.warnings || [])];
    if (value) {
      if (index < warnings.length) {
        warnings[index] = value;
      } else {
        warnings.push(value);
      }
    } else if (index < warnings.length) {
      warnings.splice(index, 1);
    }

    const entities = { ...(this._config?.entities || {}) };
    if (warnings.length) {
      entities.warnings = warnings.filter(Boolean);
    } else {
      delete entities.warnings;
    }
    this._updateConfig({ ...this._config, entities });
  }

  _updateConfig(config) {
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config },
        bubbles: true,
        composed: true,
      })
    );
  }

  static get styles() {
    return css`
      .editor {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 4px 0;
      }

      .section {
        border-top: 1px solid var(--divider-color, #e0e0e0);
        padding-top: 10px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }

      .section__title {
        font-weight: 600;
        font-size: 14px;
        color: var(--primary-text-color);
      }

      .row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }

      .row__label {
        font-weight: 500;
      }

      .hint {
        margin: 0;
        color: var(--secondary-text-color);
        font-size: 12px;
      }
    `;
  }
}

customElements.define("bluelink-kr-card-editor", BluelinkKrCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "bluelink-kr-card",
  name: "Hyundai Bluelink KR Card",
  description: "전용 블루링크 센서와 충전 상태를 표시하는 Lovelace 카드",
  preview: true,
});
