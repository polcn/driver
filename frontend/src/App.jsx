import { useEffect, useState } from "react";

const emptySnapshot = {
  date: null,
  food: null,
  activity: null,
  targets: {},
  exercise: [],
  sleep: null,
  suggestion: null,
  insights: []
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
const emptyLabs = [];
const emptyLabTrend = [];
const emptySupplements = [];
const emptyMedications = [];
const emptyDoctorReport = null;
const emptyGoals = [];

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

function buildLabSeries(entries) {
  if (entries.length === 0) {
    return [];
  }

  const values = entries.map((entry) => entry.value ?? 0);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const spread = Math.max(1, maxValue - minValue);

  return entries.map((entry) => ({
    ...entry,
    height: Math.max(14, Math.round((((entry.value ?? minValue) - minValue) / spread) * 100))
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
  const [labs, setLabs] = useState(emptyLabs);
  const [triglyceridesTrend, setTriglyceridesTrend] = useState(emptyLabTrend);
  const [glucoseTrend, setGlucoseTrend] = useState(emptyLabTrend);
  const [supplements, setSupplements] = useState(emptySupplements);
  const [medications, setMedications] = useState(emptyMedications);
  const [photoDescription, setPhotoDescription] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [photoMealType, setPhotoMealType] = useState("meal");
  const [photoCalories, setPhotoCalories] = useState("");
  const [photoProtein, setPhotoProtein] = useState("");
  const [photoAnalysisMethod, setPhotoAnalysisMethod] = useState("");
  const [photoConfidence, setPhotoConfidence] = useState("");
  const [photoStatus, setPhotoStatus] = useState("");
  const [doctorReport, setDoctorReport] = useState(emptyDoctorReport);
  const [reportDays, setReportDays] = useState(30);
  const [reportStatus, setReportStatus] = useState("");
  const [goals, setGoals] = useState(emptyGoals);
  const [goalName, setGoalName] = useState("");
  const [goalMetric, setGoalMetric] = useState("weight_lbs");
  const [goalType, setGoalType] = useState("target");
  const [goalTargetValue, setGoalTargetValue] = useState("");
  const [goalDirection, setGoalDirection] = useState("down");
  const [goalStatus, setGoalStatus] = useState("");
  const [goalPlanStatus, setGoalPlanStatus] = useState("");
  const [selectedPlanText, setSelectedPlanText] = useState("");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

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

        const [
          weightResponse,
          waistResponse,
          sleepResponse,
          sleepTrendResponse,
          labsResponse,
          triglyceridesResponse,
          glucoseResponse,
          supplementsResponse,
          medicationsResponse,
          reportResponse,
          goalsResponse,
          setsPayload
        ] = await Promise.all([
          fetch(`/api/v1/metrics/?metric=weight_lbs&days=14&ending=${todayPayload.date}`),
          fetch(`/api/v1/metrics/?metric=waist_in&days=14&ending=${todayPayload.date}`),
          fetch(`/api/v1/sleep/?recorded_date=${todayPayload.date}`),
          fetch(`/api/v1/sleep/?days=14&ending=${todayPayload.date}`),
          fetch("/api/v1/labs/"),
          fetch("/api/v1/labs/?marker=Triglycerides"),
          fetch("/api/v1/labs/?marker=Glucose"),
          fetch("/api/v1/supplements/"),
          fetch("/api/v1/medications/"),
          fetch(`/api/v1/reports/doctor-visit?days=${reportDays}&ending=${todayPayload.date}`),
          fetch("/api/v1/goals/"),
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
      if (!labsResponse.ok) {
        throw new Error(`Labs request failed: ${labsResponse.status}`);
      }
      if (!triglyceridesResponse.ok) {
        throw new Error(`Triglycerides trend request failed: ${triglyceridesResponse.status}`);
      }
      if (!glucoseResponse.ok) {
        throw new Error(`Glucose trend request failed: ${glucoseResponse.status}`);
      }
      if (!supplementsResponse.ok) {
        throw new Error(`Supplements request failed: ${supplementsResponse.status}`);
      }
      if (!medicationsResponse.ok) {
        throw new Error(`Medications request failed: ${medicationsResponse.status}`);
      }
      if (!reportResponse.ok) {
        throw new Error(`Doctor report request failed: ${reportResponse.status}`);
      }
      if (!goalsResponse.ok) {
        throw new Error(`Goals request failed: ${goalsResponse.status}`);
      }
      const weightPayload = await weightResponse.json();
      const waistPayload = await waistResponse.json();
      const sleepPayload = await sleepResponse.json();
      const sleepTrendPayload = await sleepTrendResponse.json();
      const labsPayload = await labsResponse.json();
      const triglyceridesPayload = await triglyceridesResponse.json();
      const glucosePayload = await glucoseResponse.json();
      const supplementsPayload = await supplementsResponse.json();
      const medicationsPayload = await medicationsResponse.json();
      const reportPayload = await reportResponse.json();
      const goalsPayload = await goalsResponse.json();
      const exerciseSetsPayload = Object.fromEntries(setsPayload);

      setSnapshot(todayPayload);
      setWeek(weekPayload);
      setWeightTrend(weightPayload);
      setWaistTrend(waistPayload);
      setSleepRecord(sleepPayload);
      setSleepTrend(sleepTrendPayload);
      setLabs(labsPayload);
      setTriglyceridesTrend(triglyceridesPayload);
      setGlucoseTrend(glucosePayload);
      setSupplements(supplementsPayload);
      setMedications(medicationsPayload);
      setDoctorReport(reportPayload);
      setGoals(goalsPayload);
      setExerciseSets(exerciseSetsPayload);
      setStatus("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setStatus("error");
    }
  }

  useEffect(() => {
    loadSnapshot();
  }, []);

  async function handlePhotoSubmit(event) {
    event.preventDefault();

    const recordedDate = snapshot.date ?? new Date().toISOString().slice(0, 10);
    setPhotoStatus("submitting");
    try {
      const response = await fetch("/api/v1/food/from-photo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recorded_date: recordedDate,
          meal_type: photoMealType,
          description: photoDescription,
          photo_url: photoUrl,
          servings: 1.0,
          source: "agent",
          calories: photoCalories === "" ? undefined : Number(photoCalories),
          protein_g: photoProtein === "" ? undefined : Number(photoProtein)
        })
      });
      if (!response.ok) {
        throw new Error(`Photo log request failed: ${response.status}`);
      }

      setPhotoStatus("saved");
      setPhotoDescription("");
      setPhotoUrl("");
      setPhotoCalories("");
      setPhotoProtein("");
      setPhotoAnalysisMethod("");
      setPhotoConfidence("");
      await loadSnapshot();
    } catch (err) {
      setPhotoStatus(err instanceof Error ? err.message : "submit failed");
    }
  }

  async function handlePhotoAnalyze(event) {
    event.preventDefault();
    setPhotoStatus("analyzing");
    try {
      const response = await fetch("/api/v1/food/photo-estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description: photoDescription,
          photo_url: photoUrl,
          servings: 1.0,
          use_vision: true
        })
      });
      if (!response.ok) {
        throw new Error(`Photo analyze failed: ${response.status}`);
      }
      const payload = await response.json();
      setPhotoCalories(String(payload.estimate.calories ?? ""));
      setPhotoProtein(String(payload.estimate.protein_g ?? ""));
      setPhotoAnalysisMethod(payload.analysis_method ?? "");
      setPhotoConfidence(String(payload.analysis_confidence ?? ""));
      setPhotoStatus("analyzed");
    } catch (err) {
      setPhotoStatus(err instanceof Error ? err.message : "analyze failed");
    }
  }

  async function handleRefreshReport(event) {
    event.preventDefault();
    const ending = snapshot.date ?? new Date().toISOString().slice(0, 10);
    setReportStatus("refreshing");
    try {
      const response = await fetch(`/api/v1/reports/doctor-visit?days=${reportDays}&ending=${ending}`);
      if (!response.ok) {
        throw new Error(`Report request failed: ${response.status}`);
      }
      const payload = await response.json();
      setDoctorReport(payload);
      setReportStatus("ready");
    } catch (err) {
      setReportStatus(err instanceof Error ? err.message : "refresh failed");
    }
  }

  async function handleCreateGoal(event) {
    event.preventDefault();
    const startDate = snapshot.date ?? new Date().toISOString().slice(0, 10);
    setGoalStatus("submitting");
    try {
      const payload = {
        name: goalName,
        metric: goalMetric,
        goal_type: goalType,
        start_date: startDate
      };
      if (goalType === "target") {
        payload.target_value = Number(goalTargetValue);
      } else {
        payload.direction = goalDirection;
      }
      const response = await fetch("/api/v1/goals/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error(`Goal create failed: ${response.status}`);
      }
      setGoalStatus("saved");
      setGoalName("");
      setGoalTargetValue("");
      await loadSnapshot();
    } catch (err) {
      setGoalStatus(err instanceof Error ? err.message : "submit failed");
    }
  }

  async function handleGeneratePlan(goalId) {
    setGoalPlanStatus(`generating plan for #${goalId}`);
    try {
      const response = await fetch(`/api/v1/goals/${goalId}/plans/generate`, {
        method: "POST"
      });
      if (!response.ok) {
        throw new Error(`Plan generation failed: ${response.status}`);
      }
      const payload = await response.json();
      setSelectedPlanText(payload.plan);
      setGoalPlanStatus("ready");
      await loadSnapshot();
    } catch (err) {
      setGoalPlanStatus(err instanceof Error ? err.message : "plan failed");
    }
  }

  const food = snapshot.food ?? {};
  const activity = snapshot.activity ?? {};
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
  const latestDrawDate = labs.length > 0 ? labs[0].drawn_date : null;
  const latestPanelRows = latestDrawDate ? labs.filter((row) => row.drawn_date === latestDrawDate) : [];
  const triglyceridesSeries = buildLabSeries(triglyceridesTrend.slice().reverse());
  const glucoseSeries = buildLabSeries(glucoseTrend.slice().reverse());

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

      <section className="panel insights-panel">
        <h2>Narrative insights</h2>
        {snapshot.insights.length === 0 ? (
          <p className="panel-copy">Insights will appear as more sleep, recovery, and intake history accumulates.</p>
        ) : (
          <ul className="insights-list">
            {snapshot.insights.map((insight, index) => (
              <li key={`${snapshot.date}-${index}`}>{insight}</li>
            ))}
          </ul>
        )}
      </section>

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
        <MetricCard
          label="Steps"
          value={activity.steps}
        />
        <MetricCard
          label="Active Calories"
          value={activity.active_calories}
        />
      </section>

      <section className="panel">
        <h2>Photo food quick log</h2>
        <p className="panel-copy">Analyze image + description, optionally edit macros, then log.</p>
        <form className="photo-form" onSubmit={handlePhotoSubmit}>
          <input
            value={photoDescription}
            onChange={(event) => setPhotoDescription(event.target.value)}
            placeholder="Description (e.g. protein shake, salad)"
            required
          />
          <input
            value={photoUrl}
            onChange={(event) => setPhotoUrl(event.target.value)}
            placeholder="Photo URL"
            required
          />
          <select value={photoMealType} onChange={(event) => setPhotoMealType(event.target.value)}>
            <option value="meal">meal</option>
            <option value="breakfast">breakfast</option>
            <option value="lunch">lunch</option>
            <option value="dinner">dinner</option>
            <option value="snack">snack</option>
            <option value="drink">drink</option>
          </select>
          <input
            type="number"
            step="1"
            value={photoCalories}
            onChange={(event) => setPhotoCalories(event.target.value)}
            placeholder="Calories override (optional)"
          />
          <input
            type="number"
            step="1"
            value={photoProtein}
            onChange={(event) => setPhotoProtein(event.target.value)}
            placeholder="Protein g override (optional)"
          />
          <button type="button" onClick={handlePhotoAnalyze}>Analyze Photo</button>
          <button type="submit">Log Photo Meal</button>
        </form>
        {photoAnalysisMethod ? (
          <p className="panel-copy">
            Analysis: {photoAnalysisMethod} · confidence {photoConfidence || "n/a"}
          </p>
        ) : null}
        {photoStatus ? <p className="panel-copy">Status: {photoStatus}</p> : null}
      </section>

      <section className="panel">
        <h2>Doctor visit report</h2>
        <form className="inline-form" onSubmit={handleRefreshReport}>
          <label>
            Days
            <input
              type="number"
              min="7"
              max="365"
              value={reportDays}
              onChange={(event) => setReportDays(Number(event.target.value))}
            />
          </label>
          <button type="submit">Refresh Report</button>
        </form>
        {reportStatus ? <p className="panel-copy">Status: {reportStatus}</p> : null}
        {doctorReport?.report_markdown ? (
          <pre className="report-preview">{doctorReport.report_markdown}</pre>
        ) : (
          <p className="panel-copy">No report loaded yet.</p>
        )}
      </section>

      <section className="panel">
        <h2>Goals and plans</h2>
        <form className="goal-form" onSubmit={handleCreateGoal}>
          <input
            value={goalName}
            onChange={(event) => setGoalName(event.target.value)}
            placeholder="Goal name"
            required
          />
          <input
            value={goalMetric}
            onChange={(event) => setGoalMetric(event.target.value)}
            placeholder="Metric (e.g. weight_lbs)"
            required
          />
          <select value={goalType} onChange={(event) => setGoalType(event.target.value)}>
            <option value="target">target</option>
            <option value="directional">directional</option>
          </select>
          {goalType === "target" ? (
            <input
              type="number"
              step="0.1"
              value={goalTargetValue}
              onChange={(event) => setGoalTargetValue(event.target.value)}
              placeholder="Target value"
              required
            />
          ) : (
            <select value={goalDirection} onChange={(event) => setGoalDirection(event.target.value)}>
              <option value="down">down</option>
              <option value="up">up</option>
            </select>
          )}
          <button type="submit">Create Goal</button>
        </form>
        {goalStatus ? <p className="panel-copy">Status: {goalStatus}</p> : null}
        {goalPlanStatus ? <p className="panel-copy">Plan status: {goalPlanStatus}</p> : null}
        {goals.length === 0 ? (
          <p className="panel-copy">No active goals yet.</p>
        ) : (
          <ul className="goal-list">
            {goals.map((goal) => (
              <li key={goal.id} className="goal-item">
                <div className="goal-head">
                  <strong>{goal.name}</strong>
                  <span>{goal.metric}</span>
                </div>
                <p className="panel-copy">
                  {goal.goal_type === "target"
                    ? `Target ${goal.target_value}`
                    : `Trend ${goal.direction}`}
                </p>
                <button type="button" onClick={() => handleGeneratePlan(goal.id)}>
                  Generate Plan
                </button>
              </li>
            ))}
          </ul>
        )}
        {selectedPlanText ? <pre className="report-preview">{selectedPlanText}</pre> : null}
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

      <section className="content-grid lower-grid">
        <article className="panel panel-wide-two">
          <h2>Latest labs snapshot</h2>
          {latestPanelRows.length === 0 ? (
            <p className="panel-copy">No labs logged yet. Use `/api/v1/labs` to backfill panel history.</p>
          ) : (
            <>
              <p className="panel-copy">{`Panel date ${latestDrawDate}`}</p>
              <dl className="detail-list">
                {latestPanelRows.map((row) => (
                  <div key={`${row.drawn_date}-${row.panel}-${row.marker}`}>
                    <dt>{row.marker}</dt>
                    <dd>{`${row.value} ${row.unit}${row.flag ? ` (${row.flag})` : ""}`}</dd>
                  </div>
                ))}
              </dl>
            </>
          )}
        </article>

        <article className="panel">
          <h2>Lab marker trends</h2>
          {triglyceridesSeries.length > 0 ? (
            <>
              <p className="panel-copy">Triglycerides</p>
              <div className="trend-chart trend-chart-labs" aria-label="Triglycerides trend">
                {triglyceridesSeries.map((entry) => (
                  <div key={`${entry.drawn_date}-${entry.created_at}`} className="trend-column">
                    <span className="trend-value">{entry.value}</span>
                    <span className="trend-bar trend-bar-labs" style={{ height: `${entry.height}%` }} />
                    <span className="trend-label">{entry.drawn_date.slice(5)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="panel-copy">No triglycerides history yet.</p>
          )}
          {glucoseSeries.length > 0 ? (
            <>
              <p className="panel-copy">Glucose</p>
              <div className="trend-chart trend-chart-labs" aria-label="Glucose trend">
                {glucoseSeries.map((entry) => (
                  <div key={`${entry.drawn_date}-${entry.created_at}`} className="trend-column">
                    <span className="trend-value">{entry.value}</span>
                    <span className="trend-bar trend-bar-labs" style={{ height: `${entry.height}%` }} />
                    <span className="trend-label">{entry.drawn_date.slice(5)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </article>
      </section>

      <section className="content-grid lower-grid">
        <article className="panel">
          <h2>Active supplements</h2>
          {supplements.length === 0 ? (
            <p className="panel-copy">No active supplements found.</p>
          ) : (
            <ul className="care-list">
              {supplements.map((item) => (
                <li key={item.id} className="care-item">
                  <div className="care-title-row">
                    <strong>{item.name}</strong>
                    <span className="care-dose">{item.dose}</span>
                  </div>
                  <p className="care-meta">{item.frequency || "No frequency set"}</p>
                  {item.notes ? <p className="care-note">{item.notes}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="panel">
          <h2>Active medications</h2>
          {medications.length === 0 ? (
            <p className="panel-copy">No active medications found.</p>
          ) : (
            <ul className="care-list">
              {medications.map((item) => (
                <li key={item.id} className="care-item">
                  <div className="care-title-row">
                    <strong>{item.name}</strong>
                    <span className="care-dose">{item.dose}</span>
                  </div>
                  <p className="care-meta">{item.frequency || "No frequency set"}</p>
                  <p className="care-meta">
                    {item.prescriber ? `Prescriber: ${item.prescriber}` : "No prescriber set"}
                  </p>
                  {item.notes ? <p className="care-note">{item.notes}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="panel">
          <h2>Care plan snapshot</h2>
          <dl className="detail-list">
            <div>
              <dt>Supplements</dt>
              <dd>{supplements.length}</dd>
            </div>
            <div>
              <dt>Medications</dt>
              <dd>{medications.length}</dd>
            </div>
            <div>
              <dt>Total active</dt>
              <dd>{supplements.length + medications.length}</dd>
            </div>
          </dl>
        </article>
      </section>
    </main>
  );
}

export default App;
