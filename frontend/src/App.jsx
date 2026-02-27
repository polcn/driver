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

const emptyWeightTrend = [];
const emptyWaistTrend = [];
const emptyExerciseSets = {};
const emptySleepRecord = null;
const emptySleepTrend = [];

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

function formatExerciseMeta(session) {
  const bits = [];

  if (session.duration_min != null) {
    bits.push(`${session.duration_min} min`);
  }
  if (session.calories_burned != null) {
    bits.push(`${session.calories_burned} cal`);
  }
  if (session.avg_heart_rate != null) {
    bits.push(`avg HR ${session.avg_heart_rate}`);
  }

  return bits.length > 0 ? bits.join(" · ") : "No session details yet.";
}

function isStrengthSession(session) {
  const value = `${session.session_type ?? ""} ${session.name ?? ""}`.toLowerCase();
  return (
    value.includes("strength") ||
    value.includes("push") ||
    value.includes("pull") ||
    value.includes("legs") ||
    value.includes("upper") ||
    value.includes("lower")
  );
}

function formatSetSummary(set) {
  const bits = [];

  if (set.weight_lbs != null) {
    bits.push(`${set.weight_lbs} lbs`);
  }
  if (set.reps != null) {
    bits.push(`${set.reps} reps`);
  }

  return bits.length > 0 ? bits.join(" x ") : "Logged set";
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

function buildWeightSeries(entries) {
  if (entries.length === 0) {
    return [];
  }

  const values = entries.map((entry) => entry.value ?? 0);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const spread = Math.max(1, maxValue - minValue);

  return entries.map((entry) => ({
    ...entry,
    height: Math.max(14, Math.round((((entry.value ?? minValue) - minValue) / spread) * 100)),
    offset: Number((entry.value - entries[0].value).toFixed(1))
  }));
}

function buildSleepSeries(records) {
  if (records.length === 0) {
    return [];
  }

  const values = records.map((record) => record.duration_min ?? 0);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const spread = Math.max(1, maxValue - minValue);

  return records
    .slice()
    .reverse()
    .map((record) => ({
      ...record,
      height: Math.max(
        14,
        Math.round((((record.duration_min ?? minValue) - minValue) / spread) * 100)
      )
    }));
}

function App() {
  const [snapshot, setSnapshot] = useState(emptySnapshot);
  const [week, setWeek] = useState(emptyWeek);
  const [weightTrend, setWeightTrend] = useState(emptyWeightTrend);
  const [waistTrend, setWaistTrend] = useState(emptyWaistTrend);
  const [exerciseSets, setExerciseSets] = useState(emptyExerciseSets);
  const [sleepRecord, setSleepRecord] = useState(emptySleepRecord);
  const [sleepTrend, setSleepTrend] = useState(emptySleepTrend);
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

        const [weightResponse, waistResponse, sleepResponse, sleepTrendResponse, setsPayload] = await Promise.all([
          fetch(`/api/v1/metrics?metric=weight_lbs&days=14&ending=${todayPayload.date}`),
          fetch(`/api/v1/metrics?metric=waist_in&days=14&ending=${todayPayload.date}`),
          fetch(`/api/v1/sleep?recorded_date=${todayPayload.date}`),
          fetch(`/api/v1/sleep?days=14&ending=${todayPayload.date}`),
          Promise.all(
            (todayPayload.exercise ?? [])
              .filter(isStrengthSession)
              .map(async (session) => {
                const response = await fetch(`/api/v1/exercise/sessions/${session.id}/sets`);
                if (!response.ok) {
                  throw new Error(`Exercise set request failed: ${response.status}`);
                }

                return [session.id, await response.json()];
              })
          )
        ]);
        if (!weightResponse.ok) {
          throw new Error(`Weight trend request failed: ${weightResponse.status}`);
        }
        if (!waistResponse.ok) {
          throw new Error(`Waist trend request failed: ${waistResponse.status}`);
        }
        if (!sleepResponse.ok) {
          throw new Error(`Sleep request failed: ${sleepResponse.status}`);
        }
        if (!sleepTrendResponse.ok) {
          throw new Error(`Sleep trend request failed: ${sleepTrendResponse.status}`);
        }
        const weightPayload = await weightResponse.json();
        const waistPayload = await waistResponse.json();
        const sleepPayload = await sleepResponse.json();
        const sleepTrendPayload = await sleepTrendResponse.json();
        const exerciseSetsPayload = Object.fromEntries(setsPayload);
        if (!isActive) {
          return;
        }

        setSnapshot(todayPayload);
        setWeek(weekPayload);
        setWeightTrend(weightPayload);
        setWaistTrend(waistPayload);
        setSleepRecord(sleepPayload);
        setSleepTrend(sleepTrendPayload);
        setExerciseSets(exerciseSetsPayload);
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
  const weightSeries = buildWeightSeries(weightTrend);
  const waistSeries = buildWeightSeries(waistTrend);
  const sleepSeries = buildSleepSeries(sleepTrend);
  const sleep = sleepRecord ?? snapshot.sleep;
  const exerciseSummary = formatExerciseSummary(snapshot.exercise);
  const latestWeight = weightSeries.length > 0 ? weightSeries[weightSeries.length - 1].value : null;
  const weightChange = weightSeries.length > 1 ? weightSeries[weightSeries.length - 1].offset : null;
  const latestWaist = waistSeries.length > 0 ? waistSeries[waistSeries.length - 1].value : null;
  const waistChange = waistSeries.length > 1 ? waistSeries[waistSeries.length - 1].offset : null;

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
        <article className="panel panel-wide-two">
          <div className="panel-header">
            <div>
              <h2>Weight trend</h2>
              <p className="panel-copy">
                {latestWeight == null
                  ? "No weight entries yet."
                  : `Latest ${latestWeight} lbs${weightChange == null ? "" : ` · ${weightChange > 0 ? "+" : ""}${weightChange} vs first point`}`}
              </p>
            </div>
          </div>
          {weightSeries.length === 0 ? (
            <p className="panel-copy">Log weight through `/api/v1/metrics` to populate this view.</p>
          ) : (
            <div className="trend-chart trend-chart-weight" aria-label="Weight trend">
              {weightSeries.map((entry) => (
                <div key={`${entry.recorded_date}-${entry.created_at}`} className="trend-column">
                  <span className="trend-value">{entry.value}</span>
                  <span className="trend-bar trend-bar-weight" style={{ height: `${entry.height}%` }} />
                  <span className="trend-label">{entry.recorded_date.slice(5)}</span>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="panel">
          <h2>Waist trend</h2>
          <p className="panel-value">
            {latestWaist == null ? "No entry" : `${latestWaist}"`}
          </p>
          <p className="panel-copy">
            {latestWaist == null
              ? "Log waist measurements through `/api/v1/metrics`."
              : `${waistChange == null ? "First logged measurement." : `${waistChange > 0 ? "+" : ""}${waistChange}" vs first point`}`}
          </p>
          {waistSeries.length > 0 ? (
            <div className="trend-chart trend-chart-waist" aria-label="Waist trend">
              {waistSeries.map((entry) => (
                <div key={`${entry.recorded_date}-${entry.created_at}`} className="trend-column">
                  <span className="trend-value">{entry.value}</span>
                  <span className="trend-bar trend-bar-waist" style={{ height: `${entry.height}%` }} />
                  <span className="trend-label">{entry.recorded_date.slice(5)}</span>
                </div>
              ))}
            </div>
          ) : null}
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

      <section className="content-grid">
        <article className="panel">
          <h2>Exercise</h2>
          <p className="panel-value">{snapshot.exercise.length}</p>
          <p className="panel-copy">{exerciseSummary}</p>
          {snapshot.exercise.length > 0 ? (
            <ul className="session-list">
              {snapshot.exercise.map((session) => (
                <li key={session.id} className="session-item">
                  <div className="session-title-row">
                    <strong>{session.name || session.session_type}</strong>
                    <span className="session-type">{session.session_type}</span>
                  </div>
                  <p className="session-meta">{formatExerciseMeta(session)}</p>
                  {(exerciseSets[session.id] ?? []).length > 0 ? (
                    <ul className="set-list">
                      {exerciseSets[session.id].map((set) => (
                        <li
                          key={`${set.session_id}-${set.exercise_name}-${set.set_number}-${set.id}`}
                          className="set-item"
                        >
                          <div className="set-title-row">
                            <strong>{set.exercise_name}</strong>
                            <span className="set-number">Set {set.set_number}</span>
                          </div>
                          <p className="set-meta">{formatSetSummary(set)}</p>
                          {set.notes ? <p className="set-note">{set.notes}</p> : null}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </article>

        <article className="panel">
          <h2>Sleep</h2>
          <p className="panel-value">
            {sleep?.duration_min ? `${sleep.duration_min} min` : "No sleep record"}
          </p>
          <p className="panel-copy">
            {sleep?.sleep_score
              ? `Sleep score ${sleep.sleep_score}`
              : "Sleep data will appear here once ingestion is wired."}
          </p>
          {sleepSeries.length > 0 ? (
            <div className="trend-chart trend-chart-sleep" aria-label="Sleep duration trend">
              {sleepSeries.map((record) => (
                <div key={`${record.recorded_date}-${record.created_at}`} className="trend-column">
                  <span className="trend-value">{record.duration_min ?? 0}</span>
                  <span className="trend-bar trend-bar-sleep" style={{ height: `${record.height}%` }} />
                  <span className="trend-label">{record.recorded_date.slice(5)}</span>
                </div>
              ))}
            </div>
          ) : null}
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
          <h2>Week activity</h2>
          <dl className="detail-list">
            <div>
              <dt>Food days</dt>
              <dd>{week.food_by_day.length}</dd>
            </div>
            <div>
              <dt>Exercise days</dt>
              <dd>{week.exercise_by_day.length}</dd>
            </div>
            <div>
              <dt>Total calories</dt>
              <dd>
                {week.food_by_day.reduce((sum, day) => sum + (day.calories ?? 0), 0)}
              </dd>
            </div>
            <div>
              <dt>Total protein</dt>
              <dd>
                {week.food_by_day.reduce((sum, day) => sum + (day.protein_g ?? 0), 0)}g
              </dd>
            </div>
          </dl>
        </article>
      </section>
    </main>
  );
}

export default App;
