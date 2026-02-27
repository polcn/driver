import { useEffect, useState } from "react";

const emptySnapshot = {
  date: null,
  food: null,
  targets: {},
  exercise: [],
  sleep: null,
  suggestion: null
};

function MetricCard({ label, value, target, unit }) {
  const displayValue = value ?? 0;
  const displayTarget = target ?? null;

  return (
    <article className="metric-card">
      <p className="eyebrow">{label}</p>
      <p className="metric-value">
        {displayValue}
        {unit ? <span className="metric-unit">{unit}</span> : null}
      </p>
      <p className="metric-detail">
        {displayTarget == null ? "No target set" : `Target ${displayTarget}${unit ?? ""}`}
      </p>
    </article>
  );
}

function App() {
  const [snapshot, setSnapshot] = useState(emptySnapshot);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let isActive = true;

    async function loadSnapshot() {
      try {
        const response = await fetch("/api/v1/dashboard/today");
        if (!response.ok) {
          throw new Error(`Dashboard request failed: ${response.status}`);
        }

        const payload = await response.json();
        if (!isActive) {
          return;
        }

        setSnapshot(payload);
        setStatus("ready");
      } catch (err) {
        if (!isActive) {
          return;
        }

        setError(err instanceof Error ? err.message : "Unknown error");
        setStatus("error");
      }
    }

    loadSnapshot();

    return () => {
      isActive = false;
    };
  }, []);

  const food = snapshot.food ?? {};
  const targets = snapshot.targets ?? {};

  return (
    <main className="page-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Driver</p>
          <h1>Today at a glance</h1>
          <p className="hero-copy">
            Minimal Phase 1 dashboard scaffold for food, sleep, exercise, and daily guidance.
          </p>
        </div>
        <div className="hero-status">
          <span className={`status-pill status-${status}`}>{status}</span>
          <p>{snapshot.date ? `Snapshot date ${snapshot.date}` : "Waiting for data"}</p>
        </div>
      </section>

      {status === "error" ? (
        <section className="panel">
          <h2>Backend connection problem</h2>
          <p>{error}</p>
        </section>
      ) : null}

      <section className="grid">
        <MetricCard
          label="Calories"
          value={food.calories}
          target={targets.calories}
        />
        <MetricCard
          label="Protein"
          value={food.protein_g}
          target={targets.protein_g}
          unit="g"
        />
        <MetricCard
          label="Sodium"
          value={food.sodium_mg}
          target={targets.sodium_mg}
          unit="mg"
        />
        <MetricCard
          label="Food Entries"
          value={food.entry_count}
        />
      </section>

      <section className="content-grid">
        <article className="panel">
          <h2>Exercise</h2>
          <p className="panel-value">{snapshot.exercise.length}</p>
          <p className="panel-copy">
            Logged sessions for the current day.
          </p>
        </article>

        <article className="panel">
          <h2>Sleep</h2>
          <p className="panel-value">
            {snapshot.sleep?.duration_min ? `${snapshot.sleep.duration_min} min` : "No sleep record"}
          </p>
          <p className="panel-copy">
            {snapshot.sleep?.sleep_score
              ? `Sleep score ${snapshot.sleep.sleep_score}`
              : "Sleep data will appear here once ingestion is wired."}
          </p>
        </article>

        <article className="panel panel-wide">
          <h2>Daily suggestion</h2>
          <p className="panel-copy">
            {snapshot.suggestion?.suggestion ?? "No daily suggestion has been generated yet."}
          </p>
        </article>
      </section>
    </main>
  );
}

export default App;
