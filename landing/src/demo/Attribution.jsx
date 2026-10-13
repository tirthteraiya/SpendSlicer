/* Reconcile every service's named estimates with its billed total. */

import { useMemo, useState } from "react";
import { Mark } from "@app/components/Marks.jsx";
import { usd, value } from "@app/lib/format.js";
import { SERVICES, COMPOSITION, RESOURCES, sum } from "./data";

const COMPOSITION_COLORS = {
  compute: "var(--line-1)",
  storage: "var(--line-2)",
  "data-transfer": "var(--line-4)",
  network: "var(--line-5)",
  other: "var(--line-8)",
};

const CHOICES = Object.keys(COMPOSITION);
const shortService = (n) => String(n || "").replace("Amazon ", "").replace("AWS ", "");

export function Attribution() {
  const [service, setService] = useState(CHOICES[0]);

  const view = useMemo(() => {
    const svc = SERVICES.find((s) => s.name === service);
    const usage = [...(COMPOSITION[service].usage_types || [])]
      .sort((a, b) => value(b.cost) - value(a.cost));
    const named = RESOURCES.filter((r) => r.service === service)
      .sort((a, b) => value(b.cost) - value(a.cost));
    const attributed = sum(named);
    const unattributed = Math.round((value(svc.cost) - attributed) * 100) / 100;
    return { svc, usage, named, attributed, unattributed };
  }, [service]);

  const { svc, usage, named, attributed, unattributed } = view;

  return (
    <div className="xp">
      <div className="chip-row" role="group" aria-label="Choose a service">
        {CHOICES.map((name) => (
          <button
            key={name}
            type="button"
            className={`chip ${service === name ? "on" : ""}`}
            aria-pressed={service === name}
            onClick={() => setService(name)}
          >
            {shortService(name)}
          </button>
        ))}
      </div>

      <p className="xp-sum">
        <span>{shortService(service)} billed</span>
        <b>{usd(svc.cost, 2)}</b>
        <Mark kind="exact" />
        <span className="xp-sum-note">
          in this window. Named estimates plus unattributed charges reconcile to this total.
        </span>
      </p>

      <div className="xp-cols">
        {/* ── What AWS gives you ── */}
        <section className="xp-col" aria-labelledby="xp-aws">
          <header className="xp-head">
            <h3 id="xp-aws">What AWS gives you</h3>
            <p>Usage types, priced by the hour. No machine attached.</p>
          </header>
          <table className="comp-ut-tbl xp-tbl">
            <tbody>
              {usage.map((u) => (
                <tr key={u.usage_type}>
                  <td style={{ width: 1 }}>
                    <span
                      className="comp-tag"
                      style={{ background: COMPOSITION_COLORS[u.bucket] || COMPOSITION_COLORS.other }}
                    >
                      {u.bucket}
                    </span>
                  </td>
                  <td className="id" style={{ width: "100%", wordBreak: "break-all" }}>{u.usage_type}</td>
                  <td className="num">{usd(u.cost, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="xp-foot">
            {usage.length} usage types, and not one of them names the resource behind
            the charge.
          </p>
        </section>

        {/* ── What SpendSlicer gives you ── */}
        <section className="xp-col xp-col-ours" aria-labelledby="xp-ours">
          <header className="xp-head">
            <h3 id="xp-ours">What SpendSlicer gives you</h3>
            <p>Named resource estimates, with the remainder shown separately.</p>
          </header>
          <table className="tt xp-tbl xp-tbl-res">
            <tbody>
              {named.map((r) => (
                <tr key={r.resource_id}>
                  <td className="tt-lead">
                    {r.name}
                    {r.state ? <span className="xp-state">{r.state}</span> : null}
                  </td>
                  <td className="col-id"><span className="id">{r.resource_id}</span></td>
                  <td className="num"><span className="num-strong">{usd(r.cost, 2)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl className="xp-allocation">
            <div><dt>Attributed <Mark kind="estimated" /></dt><dd>{usd(attributed, 2)}</dd></div>
            <div><dt>Unattributed <Mark kind="drift" /></dt><dd className={unattributed > 0.01 ? "is-drift" : ""}>{usd(unattributed, 2)}</dd></div>
          </dl>
          <p className="xp-foot">
            {named.length} named {named.length === 1 ? "resource" : "resources"}, each one something
            you can go and look at. Unattributed charges are never spread across these rows.
          </p>
        </section>
      </div>
    </div>
  );
}
