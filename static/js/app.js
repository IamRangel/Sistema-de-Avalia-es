const assessmentSteps = [
    { id: "tab-anamnese", title: "Anamnese", hint: "Dados do aluno e histórico" },
    { id: "tab-circ", title: "Circunferências", hint: "Registre as medidas em centímetros" },
    { id: "tab-dobras", title: "Dobras & flexibilidade", hint: "Complete as medidas e o teste de flexibilidade" },
    { id: "tab-review", title: "Revisão", hint: "Confira os dados antes de salvar" }
];

function openTab(evt, tabId) {
    setActiveAssessmentStep(assessmentSteps.findIndex(step => step.id === tabId));
}

function setActiveAssessmentStep(index) {
    if (index < 0 || index >= assessmentSteps.length) return;

    assessmentSteps.forEach((step, stepIndex) => {
        const content = document.getElementById(step.id);
        const button = document.querySelector(`.tab-btn[onclick*="${step.id}"]`);
        content.classList.toggle("active", stepIndex === index);
        if (button) {
            button.classList.toggle("active", stepIndex === index);
            button.setAttribute("aria-current", stepIndex === index ? "step" : "false");
        }
    });

    const step = assessmentSteps[index];
    document.getElementById("step-title").textContent = `Etapa ${index + 1} de ${assessmentSteps.length} · ${step.title}`;
    document.getElementById("step-hint").textContent = step.hint;
    document.querySelector(".progress-track").setAttribute("aria-valuenow", String(index + 1));
    document.getElementById("progress-value").style.width = `${((index + 1) / assessmentSteps.length) * 100}%`;
    document.getElementById("previous-step").hidden = index === 0;
    document.getElementById("next-step").hidden = index === assessmentSteps.length - 1;
    document.getElementById("submit-assessment").hidden = index !== assessmentSteps.length - 1;

    if (index === assessmentSteps.length - 1) renderAssessmentReview();
}

function validateAssessmentStep(index) {
    const panel = document.getElementById(assessmentSteps[index].id);
    const invalidField = panel.querySelector(":invalid");
    if (!invalidField) return true;

    setActiveAssessmentStep(index);
    invalidField.reportValidity();
    invalidField.focus();
    return false;
}

function renderAssessmentReview() {
    const form = document.getElementById("avaliacao-form");
    if (!form) return;

    const fields = Array.from(form.querySelectorAll(".tab-content:not(#tab-review) .form-group"))
        .map(group => {
            const checkboxes = group.querySelectorAll('input[type="checkbox"]');
            const label = group.querySelector("label");
            if (checkboxes.length) {
                const selected = Array.from(checkboxes).filter(field => field.checked).map(field => field.value);
                const other = group.querySelector('[name="objetivo_outro"]');
                const otherValue = other && !other.disabled ? other.value.trim() : "";
                if (otherValue && selected.includes("Outro")) {
                    selected[selected.indexOf("Outro")] = `Outro: ${otherValue}`;
                }

                return {
                    section: group.closest(".tab-content").id,
                    label: group.dataset.reviewLabel || (label ? label.textContent.trim() : "Opções"),
                    value: selected.join(", ") || "Não informado",
                    filled: selected.length > 0
                };
            }

            const field = group.querySelector("select, input:not([type=checkbox]), textarea");
            if (!field) return null;
            let value = field.value.trim();
            const other = group.querySelector('[name="disponibilidade_outro"]');
            const otherValue = other && !other.disabled ? other.value.trim() : "";
            if (field.tagName === "SELECT" && field.value === "Outro" && otherValue) {
                value = `Outro: ${otherValue}`;
            }

            if (!value) value = "Não informado";
            else if (field.type === "number") {
                const suffix = field.name === "peso" ? " kg"
                    : field.name === "altura" ? (Number(field.value) > 3 ? " cm" : " m")
                        : field.name === "banco_well" ? " cm"
                        : assessmentSteps[1].id === field.closest(".tab-content").id ? " cm"
                            : field.closest(".tab-content").id === "tab-dobras" && field.name !== "banco_well" ? " mm" : "";
                value += suffix;
            }

            return {
                section: field.closest(".tab-content").id,
                label: group.dataset.reviewLabel || (label ? label.textContent.replace("*", "").trim() : field.name),
                value,
                filled: field.value.trim() !== ""
            };
        })
        .filter(Boolean);

    const filledCount = fields.filter(field => field.filled).length;
    document.getElementById("review-count").textContent = `${filledCount} de ${fields.length} campos preenchidos`;

    const metricRows = [
        ["Peso", document.getElementById("peso").value ? `${document.getElementById("peso").value} kg` : "—"],
        ["Altura", document.getElementById("altura").value
            ? `${document.getElementById("altura").value}${Number(document.getElementById("altura").value) > 3 ? " cm" : " m"}`
            : "—"],
        ["IMC estimado", document.getElementById("live-imc").textContent],
        ["Gordura estimada", document.getElementById("live-bf").textContent]
    ];
    const metrics = document.getElementById("review-metrics");
    metrics.replaceChildren();
    metricRows.forEach(([label, value]) => {
        const item = document.createElement("div");
        item.className = "review-metric";
        const caption = document.createElement("span");
        caption.textContent = label;
        const result = document.createElement("strong");
        result.textContent = value;
        item.append(caption, result);
        metrics.appendChild(item);
    });

    const sections = document.getElementById("review-sections");
    sections.replaceChildren();
    assessmentSteps.slice(0, 3).forEach(step => {
        const section = document.createElement("section");
        section.className = "review-section";
        const heading = document.createElement("h3");
        heading.textContent = step.title;
        section.appendChild(heading);

        const list = document.createElement("dl");
        fields.filter(field => field.section === step.id).forEach(field => {
            const row = document.createElement("div");
            row.className = "review-row";
            const term = document.createElement("dt");
            term.textContent = field.label;
            const description = document.createElement("dd");
            description.textContent = field.value;
            row.append(term, description);
            list.appendChild(row);
        });
        section.appendChild(list);
        sections.appendChild(section);
    });
}

function renderHistoryCharts() {
    const historyElement = document.getElementById("assessment-history");
    if (!historyElement) return;

    let history;
    try {
        history = JSON.parse(historyElement.textContent);
    } catch (error) {
        console.error("Não foi possível carregar o histórico da avaliação.", error);
        return;
    }

    const svgNamespace = "http://www.w3.org/2000/svg";
    document.querySelectorAll("[data-history-chart]").forEach(chart => {
        const field = chart.dataset.field;
        const unit = chart.dataset.unit;
        const values = history
            .filter(item => item[field] !== null && item[field] !== undefined)
            .map(item => ({ date: item.data, value: Number(item[field]) }))
            .filter(item => Number.isFinite(item.value));

        if (values.length < 2) {
            chart.hidden = true;
            return;
        }

        const svg = chart.querySelector("svg");
        const plot = { left: 52, right: 620, top: 20, bottom: 174 };
        let min = Math.min(...values.map(item => item.value));
        let max = Math.max(...values.map(item => item.value));
        if (min === max) {
            const padding = Math.max(Math.abs(min) * 0.05, 1);
            min -= padding;
            max += padding;
        } else {
            const padding = (max - min) * 0.12;
            min -= padding;
            max += padding;
        }

        const yFor = value => plot.bottom - ((value - min) / (max - min)) * (plot.bottom - plot.top);
        const xFor = index => plot.left + (index / (values.length - 1)) * (plot.right - plot.left);

        [0, 0.5, 1].forEach(position => {
            const y = plot.bottom - position * (plot.bottom - plot.top);
            const gridLine = document.createElementNS(svgNamespace, "line");
            gridLine.setAttribute("x1", String(plot.left));
            gridLine.setAttribute("x2", String(plot.right));
            gridLine.setAttribute("y1", String(y));
            gridLine.setAttribute("y2", String(y));
            gridLine.setAttribute("class", "chart-grid");
            svg.appendChild(gridLine);

            const label = document.createElementNS(svgNamespace, "text");
            label.setAttribute("x", "2");
            label.setAttribute("y", String(y + 4));
            label.setAttribute("class", "chart-label");
            label.textContent = `${(min + position * (max - min)).toFixed(1)}${unit}`;
            svg.appendChild(label);
        });

        const line = document.createElementNS(svgNamespace, "polyline");
        line.setAttribute("class", "chart-line");
        line.setAttribute("points", values.map((item, index) => `${xFor(index)},${yFor(item.value)}`).join(" "));
        svg.appendChild(line);

        values.forEach((item, index) => {
            const x = xFor(index);
            const y = yFor(item.value);
            const dot = document.createElementNS(svgNamespace, "circle");
            dot.setAttribute("cx", String(x));
            dot.setAttribute("cy", String(y));
            dot.setAttribute("r", "5");
            dot.setAttribute("class", "chart-dot");
            const pointTitle = document.createElementNS(svgNamespace, "title");
            pointTitle.textContent = `${item.date}: ${item.value}${unit}`;
            dot.appendChild(pointTitle);
            svg.appendChild(dot);

            const dateLabel = document.createElementNS(svgNamespace, "text");
            dateLabel.setAttribute("x", String(x));
            dateLabel.setAttribute("y", "202");
            dateLabel.setAttribute("text-anchor", "middle");
            dateLabel.setAttribute("class", "chart-label");
            dateLabel.textContent = item.date;
            svg.appendChild(dateLabel);
        });
    });
}

function maskBirthDate(input) {
    const digitsBeforeCursor = input.value.slice(0, input.selectionStart).replace(/\D/g, "").length;
    const digits = input.value.replace(/\D/g, "").slice(0, 8);
    let formatted = digits.slice(0, 2);

    if (digits.length >= 2) formatted += "/";
    if (digits.length > 2) formatted += digits.slice(2, 4);
    if (digits.length >= 4) formatted += "/";
    if (digits.length > 4) formatted += digits.slice(4);

    input.value = formatted;
    const positionDigits = Math.min(digitsBeforeCursor, digits.length);
    let caret = positionDigits;
    if (positionDigits >= 2) caret += 1;
    if (positionDigits >= 4) caret += 1;
    input.setSelectionRange(caret, caret);
}

function maskPhoneNumber(input) {
    const digitsBeforeCursor = input.value.slice(0, input.selectionStart).replace(/\D/g, "").length;
    const digits = input.value.replace(/\D/g, "").slice(0, 11);
    let formatted = digits.length ? `(${digits.slice(0, 2)}` : "";

    if (digits.length >= 2) formatted += `)${digits.slice(2, 7)}`;
    if (digits.length > 7) formatted += ` - ${digits.slice(7)}`;

    input.value = formatted;
    const positionDigits = Math.min(digitsBeforeCursor, digits.length);
    let caret = positionDigits;
    if (positionDigits >= 1) caret += 1;
    if (positionDigits >= 2) caret += 1;
    if (positionDigits > 7) caret += 3;
    input.setSelectionRange(caret, caret);
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
    const birthDateInput = document.querySelector('input[name="data_nascimento"]');
    if (birthDateInput) {
        birthDateInput.addEventListener("input", () => maskBirthDate(birthDateInput));
        birthDateInput.addEventListener("keydown", event => {
            const cursor = birthDateInput.selectionStart;
            if (event.key !== "Backspace" || cursor !== birthDateInput.selectionEnd || cursor < 2) return;
            if (birthDateInput.value[cursor - 1] !== "/") return;

            event.preventDefault();
            birthDateInput.setRangeText("", cursor - 2, cursor - 1, "end");
            maskBirthDate(birthDateInput);
        });
    }

    const phoneInput = document.querySelector('input[name="telefone"]');
    if (phoneInput) phoneInput.addEventListener("input", () => maskPhoneNumber(phoneInput));

    document.querySelectorAll("input").forEach(inp => {
        if (inp.type === "number") inp.inputMode = "decimal";
        inp.addEventListener("input", atualizarCalculosTempoReal);
    });
    atualizarCalculosTempoReal();

    const form = document.getElementById("avaliacao-form");
    if (form) {
        const studentId = form.dataset.studentId;
        const storageKey = `avaliacao-rascunho-${studentId}`;
        const draftNotice = document.getElementById("draft-notice");
        const draftStatus = document.getElementById("draft-status");
        let saveTimer;

        const saveDraft = () => {
            const values = {};
            form.querySelectorAll("[name]").forEach(field => {
                if (field.type === "checkbox") {
                    if (!values[field.name]) values[field.name] = [];
                    if (field.checked) values[field.name].push(field.value);
                } else {
                    values[field.name] = field.value;
                }
            });
            try {
                sessionStorage.setItem(storageKey, JSON.stringify(values));
                draftStatus.textContent = "Rascunho salvo temporariamente nesta aba.";
            } catch (error) {
                console.error("Não foi possível salvar o rascunho nesta aba.", error);
                draftStatus.textContent = "Não foi possível salvar o rascunho neste navegador.";
            }
        };

        let savedDraft = null;
        const objectiveOtherCheckbox = form.querySelector('input[name="objetivo_opcoes"][value="Outro"]');
        const objectiveOtherGroup = document.getElementById("objetivo-outro-group");
        const objectiveOtherInput = document.getElementById("objetivo-outro");
        const availabilitySelect = document.getElementById("disponibilidade-treino");
        const availabilityOtherGroup = document.getElementById("disponibilidade-outro-group");
        const availabilityOtherInput = document.getElementById("disponibilidade-outro");

        const updateOptionalFields = () => {
            if (objectiveOtherCheckbox) {
                objectiveOtherGroup.hidden = !objectiveOtherCheckbox.checked;
                objectiveOtherInput.disabled = !objectiveOtherCheckbox.checked;
            }
            if (availabilitySelect) {
                const isOther = availabilitySelect.value === "Outro";
                availabilityOtherGroup.hidden = !isOther;
                availabilityOtherInput.disabled = !isOther;
            }
        };

        if (objectiveOtherCheckbox) objectiveOtherCheckbox.addEventListener("change", updateOptionalFields);
        if (availabilitySelect) availabilitySelect.addEventListener("change", updateOptionalFields);

        try {
            savedDraft = sessionStorage.getItem(storageKey);
        } catch (error) {
            console.error("Não foi possível acessar o rascunho nesta aba.", error);
            draftStatus.textContent = "O salvamento temporário não está disponível neste navegador.";
        }

        if (savedDraft) draftNotice.hidden = false;

        document.getElementById("restore-draft").addEventListener("click", () => {
            try {
                const values = JSON.parse(savedDraft);
                Object.entries(values).forEach(([name, value]) => {
                    const namedFields = Array.from(form.querySelectorAll("[name]")).filter(field => field.name === name);
                    if (!namedFields.length) return;
                    if (namedFields[0].type === "checkbox") {
                        namedFields.forEach(field => {
                            field.checked = Array.isArray(value) && value.includes(field.value);
                        });
                    } else {
                        namedFields[0].value = value;
                    }
                });
                draftNotice.hidden = true;
                updateOptionalFields();
                atualizarCalculosTempoReal();
                renderAssessmentReview();
                draftStatus.textContent = "Rascunho restaurado.";
            } catch (error) {
                console.error("Não foi possível restaurar o rascunho.", error);
                draftStatus.textContent = "Não foi possível restaurar o rascunho. Descarte-o e tente novamente.";
            }
        });

        document.getElementById("discard-draft").addEventListener("click", () => {
            try {
                sessionStorage.removeItem(storageKey);
                savedDraft = null;
                draftNotice.hidden = true;
                draftStatus.textContent = "Rascunho descartado.";
            } catch (error) {
                console.error("Não foi possível descartar o rascunho.", error);
                draftStatus.textContent = "Não foi possível descartar o rascunho neste navegador.";
            }
        });

        form.addEventListener("input", () => {
            window.clearTimeout(saveTimer);
            saveTimer = window.setTimeout(saveDraft, 400);
            atualizarCalculosTempoReal();
            renderAssessmentReview();
        });
        form.addEventListener("change", renderAssessmentReview);
        form.addEventListener("submit", event => {
            for (let index = 0; index < assessmentSteps.length - 1; index += 1) {
                if (!validateAssessmentStep(index)) {
                    event.preventDefault();
                    setActiveAssessmentStep(index);
                    return;
                }
            }
        });

        document.getElementById("previous-step").addEventListener("click", () => {
            const activeIndex = assessmentSteps.findIndex(step => document.getElementById(step.id).classList.contains("active"));
            setActiveAssessmentStep(activeIndex - 1);
        });
        document.getElementById("next-step").addEventListener("click", () => {
            const activeIndex = assessmentSteps.findIndex(step => document.getElementById(step.id).classList.contains("active"));
            if (validateAssessmentStep(activeIndex)) setActiveAssessmentStep(activeIndex + 1);
        });

        updateOptionalFields();
        setActiveAssessmentStep(0);
        renderAssessmentReview();
    }

    document.querySelectorAll("[data-fill-target]").forEach(button => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.fillTarget);
            if (!input) return;
            input.value = button.dataset.fillValue;
            input.dispatchEvent(new Event("input", { bubbles: true }));
        });
    });

    const resultDraft = document.querySelector("[data-clear-assessment-draft]");
    if (resultDraft && resultDraft.dataset.clearAssessmentDraft === "true") {
        try {
            sessionStorage.removeItem(`avaliacao-rascunho-${resultDraft.dataset.studentId}`);
        } catch (error) {
            console.error("Não foi possível limpar o rascunho após salvar a avaliação.", error);
        }
    }
    renderHistoryCharts();
});