import { AppShell } from "@/components/app-shell"

export default function BatchLoading() {
  return (
    <AppShell>
      <section className="two-col">
        <article className="panel result-card full-span">
          <div className="section-head">
            <div>
              <h3 style={{ opacity: 0.5 }}>Loading...</h3>
            </div>
          </div>
          <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>
            Loading batch analysis...
          </div>
        </article>
      </section>
    </AppShell>
  )
}
