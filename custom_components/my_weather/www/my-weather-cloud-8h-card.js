/* My-Weather eight-hour cloud chart; no external card dependencies. */
class MyWeatherCloud8hCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity || typeof config.entity !== "string") {
      throw new Error("Set entity to the My-Weather Cloud Forecast 8h sensor");
    }
    this._config = config;
    this._hours = [8, 24, 48].includes(Number(config.hours)) ? Number(config.hours) : 8;
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    this._render();
  }
  getCardSize() { return 3; }
  _render() {
    if (!this._config || !this._hass) return;
    const st = this._hass.states[this._config.entity];
    const values = st?.attributes?.forecast;
    if (!this.shadowRoot) this.attachShadow({mode:"open"});
    const root = this.shadowRoot;
    root.replaceChildren();
    const card = document.createElement("ha-card");
    const title = document.createElement("div");
    title.className = "title";
    title.textContent = this._config.title || "Bewölkung – Stundenprognose";
    card.append(title);
    const style = document.createElement("style");
    style.textContent = `
      ha-card{padding:16px;color:var(--primary-text-color);background:var(--ha-card-background,var(--card-background-color))}
      .title{font-size:var(--ha-card-header-font-size,18px);font-weight:600;margin-bottom:10px}
      .controls{display:flex;gap:6px;margin-bottom:12px}
      .controls button{font:inherit;border:1px solid var(--divider-color);border-radius:6px;padding:4px 12px;background:transparent;color:inherit;cursor:pointer}
      .controls button.active{background:var(--secondary-background-color);border-color:var(--primary-color)}
      .plot-scroll{overflow-x:auto;overscroll-behavior-x:contain}
      .plot.long{grid-template-columns:repeat(var(--hours),minmax(54px,1fr));min-width:calc(var(--hours) * 60px)}
      .plot{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:8px;height:155px;align-items:end}
      .column{min-width:0;display:flex;flex-direction:column;align-items:center;gap:5px}
      .value{font-size:12px;font-variant-numeric:tabular-nums}
      .track{height:108px;width:100%;max-width:40px;border-radius:5px;background:var(--secondary-background-color);display:flex;align-items:end;overflow:hidden}
      .bar{width:100%;background:var(--info-color,#5799d0);min-height:0;transition:height .2s}
      .hour{font-size:11px;color:var(--secondary-text-color);white-space:nowrap}
      .note{font-size:12px;margin-top:12px;color:var(--secondary-text-color)}
      .empty{color:var(--secondary-text-color);padding:35px 0}
      @media(max-width:440px){.plot{gap:3px}.value{font-size:10px}.hour{font-size:10px}}
    `;
    root.append(style);
    const controls=document.createElement("div");controls.className="controls";
    for (const hours of [8,24,48]) {
      const btn=document.createElement("button");btn.type="button";
      btn.textContent=hours+" h";btn.className=this._hours===hours?"active":"";
      btn.addEventListener("click",()=>{this._hours=hours;this._render();});
      controls.append(btn);
    }
    card.append(controls);
    if (!Array.isArray(values) || values.length === 0) {
      const empty = document.createElement("div");
      empty.className="empty";
      empty.textContent="Keine gültige Bewölkungsprognose verfügbar";
      card.append(empty);
    } else {
      const viewport=document.createElement("div");viewport.className="plot-scroll";
      const plot=document.createElement("div");plot.className="plot"+(this._hours>8?" long":"");
      plot.style.setProperty("--hours",String(this._hours));
      for (let i=0; i<Math.min(this._hours,values.length); i++) {
        const item=values[i];
        const col=document.createElement("div");col.className="column";
        const number=document.createElement("div");number.className="value";
        const val=item?.cloud_coverage;
        number.textContent=typeof val==="number" ? Math.round(val)+" %" : "–";
        const track=document.createElement("div");track.className="track";
        const bar=document.createElement("div");bar.className="bar";
        bar.style.height=typeof val==="number" && val>=0 && val<=100 ? val+"%" : "0";
        track.append(bar);
        const hour=document.createElement("div");hour.className="hour";
        if (item?.datetime) {
          const date=new Date(item.datetime);
          hour.textContent=Number.isNaN(date.getTime()) ? "–" : new Intl.DateTimeFormat(undefined,{hour:"2-digit",minute:"2-digit"}).format(date);
        } else hour.textContent="–";
        col.append(number,track,hour);plot.append(col);
      }
      viewport.append(plot);card.append(viewport);
      const note=document.createElement("div");note.className="note";
      note.textContent=`Meteonomiqs · ${values.length} h geliefert, ${values.filter(x=>typeof x.cloud_coverage==="number").length} h mit Wolkenwerten · keine zusätzliche API-Abfrage`;
      if (this._hours>values.length) note.textContent+=" · Für längere Anzeige den 48h-Sensor wählen";
      card.append(note);
    }
    root.append(card);
  }
}
if (!customElements.get("my-weather-cloud-8h-card")) {
  customElements.define("my-weather-cloud-8h-card",MyWeatherCloud8hCard);
}
window.customCards=window.customCards||[];
if (!window.customCards.some(x=>x.type==="my-weather-cloud-8h-card")) {
  window.customCards.push({type:"my-weather-cloud-8h-card",name:"My-Weather Bewölkung 8h",description:"Eight-hour Meteonomiqs cloud forecast chart"});
}
