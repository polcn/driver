import { useEffect, useState } from "react";

const emptySnapshot = {
  date: null,
  food: null,
  targets: {},
  exercise: [],
  sleep: null,
  suggestion: null
};

const emptyWeek = {
  start: null,
  end: null,
  food_by_day: [],
  exercise_by_day: []
};

function MetricCard({ label, value, target, unit }) {
  const displayValue = value ?? 0;
  const displayTarget = target ?? null;
  const progress =
    displayTarget && typeof displayValue === "number"
      ? Math.min(100, Math.round((displayValue / displayTarget) * 100))
      : null;

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
      {progress != null ? (
        <div className="progress-track" aria-hidden="true">
          <span className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      ) : null}
    </article>
  );
}

function formatExerciseSummary(exercise) {
  if (exercise.length === 0) {
    return "No workouts logged today.";
  }

  return exercise
    .map((session) => session.name || session.session_type || "Session")
    .join(" • ");
}

function buildWeeklyFoodSeries(week) {
  const maxCalories = Math.max(
    1,
    ...week.food_by_day.map((day) => day.calories ?? 0)
  );

  return week.food_by_day.map((day) => ({
    ...day,
    height: Math.max(12, Math.round(((day.calories ?? 0) / maxCalories) * 100))
  }));
}

function App() {
  const [snapshot, setSnapshot] = useState(emptySnapshot);
  const [week, setWeek] = useState(emptyWeek);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let isActive = true;

    async function loadSnapshot() {
      try {
        const [todayResponse, weekResponse] = await Promise.all([
          fetch("/api/v1/dashboard/today"),
          fetch("/api/v1/dashboard/week")
        ]);

        if (!todayResponse.ok) {
          throw new Error(`Today dashboard request failed: ${todayResponse.status}`);
        }
        if (!weekResponse.ok) {
          throw new Error(`Week dashboard request failed: ${weekResponse.status}`);
        }

        const [todayPayload, weekPayload] = await Promise.all([
          todayResponse.json(),
          weekResponse.json()
        ]);
        if (!isActive) {
          return;
        }

        setSnapshot(todayPayload);
        setWeek(weekPayload);
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
  const weeklyFood = buildWeeklyFoodSeries(week);
  const exerciseSummary = formatExerciseSummary(snapshot.exercise);

  return (
    <main className="page-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Driver</p>
          <h1>Today at a glance</h1>
          <p className="hero-copy">
            Early dashboard slice for daily intake, current recovery status, and the last 7 days of momentum.
          </p>
        </div>
        <div className="hero-status">
          <span className={`status-pill status-${status}`}>{status}</span>
          <p>{snapshot.date ? `Snapshot date ${snapshot.date}` : "Waiting for data"}</p>
          {week.start && week.end ? <p>{`Week window ${week.start} to ${week.end}`}</p> : null}
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
          <p className="panel-copy">{exerciseSummary}</p>
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

      <section className="content-grid lower-grid">
        <article className="panel panel-wide-two">
          <h2>7-day intake trend</h2>
          {weeklyFood.length === 0 ? (
            <p className="panel-copy">No weekly food history yet.</p>
          ) : (
            <div className="trend-chart" aria-label="7 day calorie trend">
              {weeklyFood.map((day) => (
                <div key={day.recorded_date} className="trend-column">
                  <span className="trend-value">{day.calories ?? 0}</span>
                  <span className="trend-bar" style={{ height: `${day.height}%` }} />
                  <span className="trend-label">{day.recorded_date.slice(5)}</span>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="panel">
          <h2>Current balance</h2>
          <dl className="detail-list">
            <div>
              <dt>Carbs</dt>
              <dd>{food.carbs_g ?? 0}g</dd>
            </div>
            <div>
              <dt>Fat</dt>
              <dd>{food.fat_g ?? 0}g</dd>
            </div>
            <div>
              <dt>Fiber</dt>
              <dd>{food.fiber_g ?? 0}g</dd>
            </div>
            <div>
              <dt>Alcohol cals</dt>
              <dd>{food.alcohol_calories ?? 0}</dd>
            </div>
          </dl>
        </article>
      </section>
    </main>
  );
}

export default App;
