const databaseToggle = document.querySelector("#databaseToggle");
const predictionToggle = document.querySelector("#predictionToggle");
const databaseStatus = document.querySelector("#databaseStatus");
const predictionStatus = document.querySelector("#predictionStatus");

const formatNumber = (value) => Number(value || 0).toLocaleString();

const labelForChurn = (value) => {
    if (value === null || value === undefined) return "N/A";
    return Number(value) === 1 ? "Churn" : "Not Churn";
};

const badge = (text, type = "neutral") => `<span class="badge ${type}">${text}</span>`;

async function postJson(url) {
    const response = await fetch(url, { method: "POST" });
    if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.error || "Request failed");
    }
    return response.json();
}

async function getJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Request failed");
    return response.json();
}

function setButtonState(button, process, startText, stopText) {
    const running = Boolean(process && process.running);
    button.classList.toggle("stop", running);
    button.querySelector("span:last-child").textContent = running ? stopText : startText;
    button.querySelector(".button-icon").textContent = running ? "x" : ">";
}

function setStatus(element, process, runningText, stoppedText) {
    const running = Boolean(process && process.running);
    element.classList.toggle("running", running);
    element.textContent = running ? runningText : stoppedText;
}

function renderStats(stats) {
    document.querySelector("#totalCustomers").textContent = formatNumber(stats.total_customers);
    document.querySelector("#totalPredictions").textContent = formatNumber(stats.total_predictions);
    document.querySelector("#correctPredictions").textContent = formatNumber(stats.correct_predictions);
    document.querySelector("#accuracy").textContent = stats.accuracy === null ? "N/A" : `${stats.accuracy}%`;
    document.querySelector("#churnCount").textContent = formatNumber(stats.prediction_churn);
    document.querySelector("#notChurnCount").textContent = formatNumber(stats.predicted_not_churn);
    document.querySelector("#churnRate").textContent = `${stats.churn_rate}% churn`;

    const total = Number(stats.total_predictions || 0);
    const churnWidth = total ? (Number(stats.prediction_churn) / total) * 100 : 0;
    const notChurnWidth = total ? (Number(stats.predicted_not_churn) / total) * 100 : 0;
    document.querySelector("#churnBar").style.width = `${churnWidth}%`;
    document.querySelector("#notChurnBar").style.width = `${notChurnWidth}%`;

    setButtonState(databaseToggle, stats.processes.database, "Start Database", "Stop Database");
    setButtonState(predictionToggle, stats.processes.prediction, "Run Predictor", "Stop Predictor");
    setStatus(databaseStatus, stats.processes.database, "Database running", "Database stopped");
    setStatus(predictionStatus, stats.processes.prediction, "Predictor running", "Predictor stopped");
    document.querySelector("#lastUpdated").textContent = new Date().toLocaleTimeString();
}

function renderCustomers(customers) {
    const body = document.querySelector("#customersTable");

    if (!customers.length) {
        body.innerHTML = `<tr><td colspan="6">No customers yet.</td></tr>`;
        return;
    }

    body.innerHTML = customers.map((customer) => `
        <tr>
            <td>${customer.CustomerID}</td>
            <td>${customer.Gender}</td>
            <td>${customer.Age}</td>
            <td>${customer.Subscription_Type}</td>
            <td>${customer.Contract_Length}</td>
            <td>${badge(labelForChurn(customer.Actual_Churn))}</td>
        </tr>
    `).join("");
}

function renderPredictions(predictions) {
    const body = document.querySelector("#predictionsTable");

    if (!predictions.length) {
        body.innerHTML = `<tr><td colspan="5">No predictions yet.</td></tr>`;
        return;
    }

    body.innerHTML = predictions.map((prediction) => {
        const correct = prediction.Is_Correct;
        let correctness = badge("N/A");

        if (correct !== null && correct !== undefined) {
            correctness = Number(correct) === 1 ? badge("Correct", "good") : badge("Wrong", "bad");
        }

        return `
            <tr>
                <td>${prediction.PredictionID}</td>
                <td>${prediction.CustomerID}</td>
                <td>${badge(labelForChurn(prediction.Prediction), Number(prediction.Prediction) === 1 ? "bad" : "good")}</td>
                <td>${Math.round(Number(prediction.Probability || 0) * 100)}%</td>
                <td>${correctness}</td>
            </tr>
        `;
    }).join("");
}

async function refreshDashboard() {
    try {
        const [stats, customers, predictions] = await Promise.all([
            getJson("/statistics"),
            getJson("/customers?limit=8"),
            getJson("/predictions?limit=8"),
        ]);

        renderStats(stats);
        renderCustomers(customers);
        renderPredictions(predictions);
    } catch (error) {
        document.querySelector("#lastUpdated").textContent = error.message;
    }
}

async function toggleProcess(name, button) {
    button.disabled = true;
    try {
        await postJson(`/api/process/${name}/toggle`);
        await refreshDashboard();
    } finally {
        button.disabled = false;
    }
}

databaseToggle.addEventListener("click", () => toggleProcess("database", databaseToggle));
predictionToggle.addEventListener("click", () => toggleProcess("prediction", predictionToggle));

refreshDashboard();
setInterval(refreshDashboard, 2500);
