let currentStorageId = "";
let currentPath = "";
let fileData = [];
let activeReadonly = false;

function $$(sel) { return document.querySelector(sel); }
function $$All(sel) { return document.querySelectorAll(sel); }

function showToast(msg, isError = false) {
  let toast = $$("#toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.className = "toast" + (isError ? " error" : "");
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3500);
}

async function switchStorage(storageId) {
  currentStorageId = storageId;
  currentPath = "";
  if (!storageId) {
    $$("#empty-state").classList.remove("hidden");
    $$("#file-view").classList.add("hidden");
    return;
  }
  const select = $$("#storage-select");
  const opt = select.options[select.selectedIndex];
  activeReadonly = opt.dataset.readonly === "true";

  $$("#empty-state").classList.add("hidden");
  $$("#file-view").classList.remove("hidden");

  if (activeReadonly) {
    $$("#upload-zone").classList.add("hidden");
    $$("#mkdir-btn").classList.add("hidden");
  } else {
    $$("#upload-zone").classList.remove("hidden");
    $$("#mkdir-btn").classList.remove("hidden");
  }

  await loadFiles();
}

async function loadFiles() {
  if (!currentStorageId) return;
  $$("#loading").classList.remove("hidden");
  $$("#empty-dir").classList.add("hidden");
  $$("#file-body").innerHTML = "";

  try {
    const res = await fetch(`/api/storages/${currentStorageId}/browse?path=${encodeURIComponent(currentPath)}`);
    if (!res.ok) throw new Error(await res.text());
    fileData = await res.json();
    renderFiles();
    updateBreadcrumbs();
  } catch (err) {
    showToast("Failed to load directory: " + err.message, true);
  } finally {
    $$("#loading").classList.add("hidden");
  }
}

function renderFiles() {
  const tbody = $$("#file-body");
  tbody.innerHTML = "";

  const search = $$("#search").value.toLowerCase();
  const sortKey = $$("#sort-select").value;
  const desc = $$("#sort-desc").checked;

  let filtered = fileData.filter(f => f.name.toLowerCase().includes(search));

  filtered.sort((a, b) => {
    // Directories first
    if (a.is_dir && !b.is_dir) return -1;
    if (!a.is_dir && b.is_dir) return 1;

    let valA = a[sortKey];
    let valB = b[sortKey];
    if (typeof valA === "string") valA = valA.toLowerCase();
    if (typeof valB === "string") valB = valB.toLowerCase();

    if (valA < valB) return desc ? 1 : -1;
    if (valA > valB) return desc ? -1 : 1;
    return 0;
  });

  if (filtered.length === 0) {
    $$("#empty-dir").classList.remove("hidden");
    return;
  } else {
    $$("#empty-dir").classList.add("hidden");
  }

  for (const item of filtered) {
    const tr = document.createElement("tr");
    const iconClass = item.is_dir ? "icon-dir" : "icon-file";
    const iconSymbol = item.is_dir ? "📁" : "📄";

    const nameCell = document.createElement("td");
    const link = document.createElement("a");
    link.href = "#";
    link.innerHTML = `<span class="${iconClass}">${iconSymbol}</span> ${item.name}`;
    link.onclick = (e) => {
      e.preventDefault();
      if (item.is_dir) {
        currentPath = item.path;
        loadFiles();
      } else {
        window.location.href = item.download_url;
      }
    };
    nameCell.appendChild(link);

    const typeCell = document.createElement("td");
    typeCell.textContent = item.is_dir ? "Folder" : "File";

    const sizeCell = document.createElement("td");
    sizeCell.textContent = item.size;

    const modifiedCell = document.createElement("td");
    modifiedCell.textContent = item.last_modified ? new Date(item.last_modified).toLocaleString() : "";

    const actionsCell = document.createElement("td");
    actionsCell.className = "actions-col";

    if (!activeReadonly) {
      const renameBtn = document.createElement("button");
      renameBtn.className = "btn-ghost";
      renameBtn.textContent = "✎";
      renameBtn.title = "Rename";
      renameBtn.onclick = () => openRenameDialog(item);
      actionsCell.appendChild(renameBtn);

      const delBtn = document.createElement("button");
      delBtn.className = "btn-danger";
      delBtn.textContent = "🗑";
      delBtn.title = "Delete";
      delBtn.onclick = () => confirmDelete(item);
      actionsCell.appendChild(delBtn);
    } else {
      const dlBtn = document.createElement("a");
      dlBtn.className = "btn-ghost";
      dlBtn.textContent = "⬇";
      dlBtn.href = item.download_url;
      dlBtn.title = "Download";
      actionsCell.appendChild(dlBtn);
    }

    tr.appendChild(nameCell);
    tr.appendChild(typeCell);
    tr.appendChild(sizeCell);
    tr.appendChild(modifiedCell);
    tr.appendChild(actionsCell);
    tbody.appendChild(tr);
  }
}

function updateBreadcrumbs() {
  const bc = $$("#breadcrumbs");
  bc.innerHTML = "";

  const rootSpan = document.createElement("span");
  rootSpan.id = "crumb-root";
  rootSpan.textContent = "Root";
  rootSpan.onclick = () => {
    currentPath = "";
    loadFiles();
  };
  bc.appendChild(rootSpan);

  if (!currentPath) return;

  const parts = currentPath.split("/");
  let acc = "";
  for (const part of parts) {
    if (!part) continue;
    acc = acc ? acc + "/" + part : part;
    const sep = document.createTextNode(" / ");
    bc.appendChild(sep);
    const span = document.createElement("span");
    span.textContent = part;
    const p = acc;
    span.onclick = () => {
      currentPath = p;
      loadFiles();
    };
    bc.appendChild(span);
  }

  $$("#dest-info").textContent = `Current destination: /${currentPath}`;
}

// Upload handling
document.addEventListener("DOMContentLoaded", () => {
  const dropZone = $$("#upload-zone");
  const fileInput = $$("#file-input");
  const browseBtn = $$("#browse-btn");

  if (browseBtn && fileInput) {
    browseBtn.onclick = () => fileInput.click();
    fileInput.onchange = (e) => handleFiles(e.target.files);
  }

  if (dropZone) {
    dropZone.ondragover = (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    };
    dropZone.ondragleave = () => dropZone.classList.remove("dragover");
    dropZone.drop = (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
      handleFiles(e.dataTransfer.files);
    };
  }

  $$("#refresh").onclick = () => loadFiles();
  $$("#search").oninput = () => renderFiles();
  $$("#sort-select").onchange = () => renderFiles();
  $$("#sort-desc").onchange = () => renderFiles();

  $$("#mkdir-btn").onclick = () => {
    $$("#mkdir-input").value = "";
    $$("#mkdir-dialog").classList.remove("hidden");
    $$("#mkdir-input").focus();
  };
  $$("#mkdir-cancel").onclick = () => $$("#mkdir-dialog").classList.add("hidden");
  $$("#mkdir-ok").onclick = async () => {
    const name = $$("#mkdir-input").value.trim();
    if (!name) return;
    const path = currentPath ? currentPath + "/" + name : name;
    try {
      const formData = new URLSearchParams();
      formData.append("path", path);
      const res = await fetch(`/api/storages/${currentStorageId}/mkdir`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(await res.text());
      $$("#mkdir-dialog").classList.add("hidden");
      showToast("Directory created successfully.");
      loadFiles();
    } catch (e) {
      showToast("Failed to create directory: " + e.message, true);
    }
  };
});

async function handleFiles(files) {
  if (!files || files.length === 0) return;
  if (activeReadonly) {
    showToast("Storage is read-only.", true);
    return;
  }

  for (const file of files) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("path", currentPath);

    showToast(`Uploading ${file.name}...`);
    try {
      const res = await fetch(`/api/storages/${currentStorageId}/upload`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(await res.text());
      showToast(`Uploaded ${file.name} successfully.`);
    } catch (e) {
      showToast(`Upload failed for ${file.name}: ${e.message}`, true);
    }
  }
  loadFiles();
}

let activeItem = null;
function openRenameDialog(item) {
  activeItem = item;
  $$("#rename-input").value = item.name;
  $$("#rename-dialog").classList.remove("hidden");
  $$("#rename-input").focus();
}

$$("#rename-cancel").onclick = () => $$("#rename-dialog").classList.add("hidden");
$$("#rename-ok").onclick = async () => {
  const newName = $$("#rename-input").value.trim();
  if (!newName || !activeItem) return;
  const parent = currentPath;
  const oldPath = activeItem.path;
  const newPath = parent ? parent + "/" + newName : newName;

  try {
    const formData = new URLSearchParams();
    formData.append("old_path", oldPath);
    formData.append("new_path", newPath);
    const res = await fetch(`/api/storages/${currentStorageId}/rename`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    $$("#rename-dialog").classList.add("hidden");
    showToast("Renamed successfully.");
    loadFiles();
  } catch (e) {
    showToast("Rename failed: " + e.message, true);
  }
};

function confirmDelete(item) {
  activeItem = item;
  $$("#confirm-title").textContent = "Confirm Delete";
  $$("#confirm-message").textContent = `Are you sure you want to delete "${item.name}"?`;
  $$("#confirm-dialog").classList.remove("hidden");
  $$("#confirm-cancel").onclick = () => $$("#confirm-dialog").classList.add("hidden");
  $$("#confirm-ok").onclick = async () => {
    try {
      const res = await fetch(`/api/storages/${currentStorageId}/item?path=${encodeURIComponent(item.path)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await res.text());
      $$("#confirm-dialog").classList.add("hidden");
      showToast("Deleted successfully.");
      loadFiles();
    } catch (e) {
      showToast("Delete failed: " + e.message, true);
    }
  };
}
