// DOM要素の取得
const todoInput = document.getElementById('todoInput');
const addBtn = document.getElementById('addBtn');
const todoList = document.getElementById('todoList');
const filterBtns = document.querySelectorAll('.filter-btn');
const totalCount = document.getElementById('totalCount');
const activeCount = document.getElementById('activeCount');
const completedCount = document.getElementById('completedCount');

// タスクデータ
let todos = [];
let currentFilter = 'all';

// LocalStorageキー
const STORAGE_KEY = 'todos';

// 初期化
function init() {
    loadFromStorage();
    renderTodos();
    updateStats();
}

// LocalStorageからデータを読み込み
function loadFromStorage() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
        try {
            todos = JSON.parse(stored);
        } catch (e) {
            console.error('データの読み込みに失敗しました:', e);
            todos = [];
        }
    }
}

// LocalStorageにデータを保存
function saveToStorage() {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
    } catch (e) {
        console.error('データの保存に失敗しました:', e);
    }
}

// タスクを追加
function addTodo() {
    const text = todoInput.value.trim();

    if (text === '') {
        alert('タスクを入力してください');
        return;
    }

    const todo = {
        id: Date.now(),
        text: text,
        completed: false,
        createdAt: new Date().toISOString()
    };

    todos.push(todo);
    todoInput.value = '';

    saveToStorage();
    renderTodos();
    updateStats();
}

// タスクを削除
function deleteTodo(id) {
    todos = todos.filter(todo => todo.id !== id);
    saveToStorage();
    renderTodos();
    updateStats();
}

// タスクの完了状態を切り替え
function toggleTodo(id) {
    const todo = todos.find(todo => todo.id === id);
    if (todo) {
        todo.completed = !todo.completed;
        saveToStorage();
        renderTodos();
        updateStats();
    }
}

// フィルタリングされたタスクを取得
function getFilteredTodos() {
    switch (currentFilter) {
        case 'active':
            return todos.filter(todo => !todo.completed);
        case 'completed':
            return todos.filter(todo => todo.completed);
        default:
            return todos;
    }
}

// タスクリストをレンダリング
function renderTodos() {
    const filteredTodos = getFilteredTodos();

    if (filteredTodos.length === 0) {
        todoList.innerHTML = '<li class="empty-state">タスクがありません</li>';
        return;
    }

    todoList.innerHTML = filteredTodos.map(todo => `
        <li class="todo-item ${todo.completed ? 'completed' : ''}">
            <input
                type="checkbox"
                class="todo-checkbox"
                ${todo.completed ? 'checked' : ''}
                onchange="toggleTodo(${todo.id})"
            >
            <span class="todo-text">${escapeHtml(todo.text)}</span>
            <button class="delete-btn" onclick="deleteTodo(${todo.id})">削除</button>
        </li>
    `).join('');
}

// 統計情報を更新
function updateStats() {
    const total = todos.length;
    const active = todos.filter(todo => !todo.completed).length;
    const completed = todos.filter(todo => todo.completed).length;

    totalCount.textContent = `全タスク: ${total}`;
    activeCount.textContent = `未完了: ${active}`;
    completedCount.textContent = `完了: ${completed}`;
}

// HTMLエスケープ（XSS対策）
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// フィルター切り替え
function setFilter(filter) {
    currentFilter = filter;

    // アクティブなボタンのスタイルを更新
    filterBtns.forEach(btn => {
        if (btn.dataset.filter === filter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    renderTodos();
}

// イベントリスナーの設定
addBtn.addEventListener('click', addTodo);

todoInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        addTodo();
    }
});

filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        setFilter(btn.dataset.filter);
    });
});

// 初期化実行
init();
