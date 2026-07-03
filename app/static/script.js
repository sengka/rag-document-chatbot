const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const uploadStatus = document.getElementById("uploadStatus");
const filesSection = document.getElementById("filesSection");
const chatBox = document.getElementById("chatBox");
const questionInput = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");

function addMessage(text, sender) {
    const msg = document.createElement("div");
    msg.classList.add("message", sender);
    msg.textContent = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function loadFiles() {
    try {
        const response = await fetch("/files");
        const data = await response.json();

        filesSection.innerHTML = "";

        if (data.files.length === 0) {
            filesSection.innerHTML = "<em>Henüz doküman yüklenmedi.</em>";
            return;
        }

        data.files.forEach((filename) => {
            const label = document.createElement("label");
            label.classList.add("file-checkbox");

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = filename;
            checkbox.checked = true;

            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(filename));
            filesSection.appendChild(label);
        });
    } catch (err) {
        filesSection.innerHTML = "<em>Dosya listesi alınamadı.</em>";
    }
}

function getSelectedSources() {
    const checkboxes = filesSection.querySelectorAll("input[type='checkbox']:checked");
    return Array.from(checkboxes).map((cb) => cb.value);
}

uploadBtn.addEventListener("click", async () => {
    const file = fileInput.files[0];

    if (!file) {
        uploadStatus.textContent = "Lütfen önce bir dosya seç.";
        return;
    }

    uploadStatus.textContent = "Yükleniyor...";
    uploadBtn.disabled = true;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Yükleme başarısız oldu.");
        }

        uploadStatus.textContent = `✓ ${data.filename} yüklendi (${data.chunk_count} parça)`;
        loadFiles();
    } catch (err) {
        uploadStatus.textContent = `Hata: ${err.message}`;
    } finally {
        uploadBtn.disabled = false;
    }
});

sendBtn.addEventListener("click", async () => {
    const question = questionInput.value.trim();

    if (!question) return;

    addMessage(question, "user");
    questionInput.value = "";
    sendBtn.disabled = true;

    const selectedSources = getSelectedSources();

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                sources: selectedSources.length > 0 ? selectedSources : null,
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Bir hata oluştu.");
        }

        let answerText = data.answer;
        if (data.sources && data.sources.length > 0) {
            answerText += `\n\nKaynak: ${data.sources.join(", ")}`;
        }

        addMessage(answerText, "bot");
    } catch (err) {
        addMessage(`Hata: ${err.message}`, "bot");
    } finally {
        sendBtn.disabled = false;
    }
});

questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        sendBtn.click();
    }
});

loadFiles();