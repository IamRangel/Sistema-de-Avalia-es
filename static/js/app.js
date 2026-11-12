function openTab(evt, tabId) {
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));
    document.getElementById(tabId).classList.add("active");
    evt.currentTarget.classList.add("active");
}

function atualizarCalculosTempoReal() {
    const pesoEl = document.getElementById("peso");
    const alturaEl = document.getElementById("altura");
    if (!pesoEl || !alturaEl) return;

    const peso = parseFloat(pesoEl.value.replace(",", "."));
    let altura = parseFloat(alturaEl.value.replace(",", "."));
    if (altura > 3) altura = altura / 100;

    const imcOut = document.getElementById("live-imc");
    if (peso > 0 && altura > 0) {
        const imc = (peso / (altura * altura)).toFixed(2);
        imcOut.textContent = imc;
    } else {
        imcOut.textContent = "--";
    }

    // Cálculo Pollock 7 Dobras em Tempo Real
    const sexo = document.getElementById("aluno-sexo").value;
    const idade = parseInt(document.getElementById("aluno-idade").value, 10);
    const ids7 = [
        "dobra_peitoral", "dobra_axilar", "dobra_triceps",
        "dobra_subescapular", "dobra_abdominal", "dobra_suprailiaca", "dobra_coxa"
    ];

    let soma = 0;
    let completas = true;
    for (const id of ids7) {
        const val = parseFloat(document.getElementById(id).value.replace(",", "."));
        if (!val || val <= 0) {
            completas = false;
            break;
        }
        soma += val;
    }

    const bfOut = document.getElementById("live-bf");
    if (completas && idade > 0) {
        let dc = 0;
        if (sexo === "M") {
            dc = 1.112 - (0.00043499 * soma) + (0.00000055 * soma * soma) - (0.00028826 * idade);
        } else {
            dc = 1.097 - (0.00046971 * soma) + (0.00000056 * soma * soma) - (0.00012828 * idade);
        }
        if (dc > 0) {
            const bf = ((495 / dc) - 450).toFixed(2);
            bfOut.textContent = `${bf}%`;
            return;
        }
    }
    bfOut.textContent = "--";
}

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input").forEach(inp => {
        inp.addEventListener("input", atualizarCalculosTempoReal);
    });
    atualizarCalculosTempoReal();
});