// ==========================================
// 1. 상태 관리 (State)
// ==========================================
const state = {
  user: {
    authType: localStorage.getItem('user_auth') || null,
    bells: parseInt(localStorage.getItem('study_bells') || '20')
  },
  selectedProfile: JSON.parse(localStorage.getItem('selected_profile') || JSON.stringify({
    character: '/AI-study/sample1.jpg',
    background: '/AI-study/sample24.jpg',
    frame: '/AI-study/sample39.jpg'
  })),
  timer: {
    isRunning: false,
    isPaused: false,
    durationSeconds: 25 * 60,
    remainingSeconds: 25 * 60,
    intervalId: null
  },
  plannerData: null
};

// ==========================================
// 2. 온보딩 & 기본 프로필 세팅
// ==========================================
window.onload = () => {
  const today = new Date();
  const futureDate = new Date();
  futureDate.setDate(today.getDate() + 30);

  const todayStr = today.toISOString().split('T')[0];
  const futureStr = futureDate.toISOString().split('T')[0];

  const dateInput = document.getElementById('input-date');
  if (dateInput) {
    dateInput.value = futureStr;
    dateInput.min = todayStr;
  }

  const bellCountEl = document.getElementById('user-bell-count');
  if (bellCountEl) {
    bellCountEl.innerText = `🔔 ${state.user.bells} 벨`;
  }

  renderHeaderProfile();
  updateTimerDisplay();
};

function selectAuthType(type) {
  state.user.authType = type; // 'google' 또는 'guest'
  localStorage.setItem('user_auth', type);
  document.getElementById('step-auth').classList.add('hidden');
  document.getElementById('step-profile-custom').classList.remove('hidden');
}

function finalizeProfileSelection(charFile, bgFile, frameFile) {
  state.selectedProfile.character = charFile;
  state.selectedProfile.background = bgFile;
  state.selectedProfile.frame = frameFile;
  localStorage.setItem('selected_profile', JSON.stringify(state.selectedProfile));

  // 메인 플래너 진입 및 상단 프로필 렌더링
  renderHeaderProfile();
  document.getElementById('step-profile-custom').classList.add('hidden');
  document.getElementById('main-planner-view').classList.remove('hidden');
}

function renderHeaderProfile() {
  const profileContainer = document.getElementById('user-profile-icon');
  if (!profileContainer) return;

  profileContainer.innerHTML = `
    <div class="profile-stack" style="position: relative; width: 75px; height: 75px;">
      <img src="${state.selectedProfile.background}" class="layer-bg" style="position: absolute; z-index: 1; width: 100%; border-radius: 50%;" onerror="this.src='/AI-study/sample24.jpg'">
      <img src="${state.selectedProfile.character}" class="layer-char" style="position: absolute; z-index: 2; width: 85%; height: 85%; top: 7.5%; left: 7.5%;" onerror="this.src='/AI-study/sample1.jpg'">
      <img src="${state.selectedProfile.frame}" class="layer-frame" style="position: absolute; z-index: 3; width: 100%;" onerror="this.src='/AI-study/sample39.jpg'">
    </div>
  `;
}

// ==========================================
// 3. AI 학습 플래너 생성 & 하단 프리뷰
// ==========================================
async function generateAiPlanner() {
  const goal = document.getElementById('input-goal') ? document.getElementById('input-goal').value.trim() : '정보처리기사 실기 합격';
  const targetDate = document.getElementById('input-date') ? document.getElementById('input-date').value.trim() : '';
  const level = document.getElementById('input-level') ? document.getElementById('input-level').value.trim() : '비전공자 기초';

  if (!goal) {
    alert('학습 목표를 입력해 주세요!');
    return;
  }
  if (!targetDate) {
    alert('목표 시험일을 선택해 주세요!');
    return;
  }

  const previewArea = document.getElementById('planner-preview-area');
  const confirmActionBox = document.getElementById('planner-confirm-box');

  previewArea.innerHTML = `<div style="text-align: center; padding: 20px; font-weight: bold; color: var(--ac-green);">🌱 최신 시험 정보 수집 및 Gemini 3.5 AI 플래너를 생성하고 있습니다...</div>`;
  previewArea.classList.remove('hidden');

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal: goal,
        exam_date: targetDate,
        level: level,
        daily_time: '3시간',
        weakness: '기출문제 및 핵심 암기',
        study_style: '개념 요약 후 기출 반복'
      })
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || '플래너 생성 중 오류가 발생했습니다.');
    }

    state.plannerData = data;
    const parsedMd = window.marked ? marked.parse(data.planner) : data.planner;

    const resultPlannerHtml = `
      <div class="planner-card">
        <h3>🎯 ${goal} 맞춤 학습 플래너</h3>
        <p>목표일: ${targetDate} (D-${data.d_day}일) | 수준: ${level}</p>
        <div class="markdown-content">
          ${parsedMd}
        </div>
      </div>
    `;

    // 1. 생성된 플래너 입력 폼 하단에 즉시 표시
    previewArea.innerHTML = resultPlannerHtml;
    previewArea.classList.remove('hidden');

    // 2. 확정 및 내보내기 버튼 영역을 생성 플래너 바로 아래 표시
    confirmActionBox.classList.remove('hidden');

    // 체크리스트 파싱 반영
    parseTodoListFromPlan(data.planner);

    // 결과 위치로 스크롤 이동
    previewArea.scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    previewArea.innerHTML = `<div style="color: red; padding: 15px;">❌ 생성 실패: ${err.message}</div>`;
  }
}

function parseTodoListFromPlan(text) {
  const lines = text.split('\n');
  const tasks = [];
  for (const line of lines) {
    const m = line.match(/^[\s\*\-]*\[\s*\]\s*(.+)$/);
    if (m) tasks.push(m[1].trim());
  }

  const todoListEl = document.querySelector('.todo-list');
  if (todoListEl && tasks.length > 0) {
    todoListEl.innerHTML = tasks.slice(0, 5).map((t, i) => `
      <label>
        <input type="checkbox" class="todo-checkbox" ${state.timer.isRunning ? '' : 'disabled'}>
        ${i+1}. ${t}
      </label>
    `).join('');
  }
}

function confirmPlanYes() {
  document.getElementById('planner-confirm-box').classList.add('hidden');
  state.user.bells += 5;
  localStorage.setItem('study_bells', state.user.bells);
  document.getElementById('user-bell-count').innerText = `🔔 ${state.user.bells} 벨`;

  alert('✨ AI 맞춤 수험 플래너가 확정되었습니다! (+5벨 보너스 획득)');
  document.querySelector('.timer-section').scrollIntoView({ behavior: 'smooth' });
}

// 내보내기/복사 기능
function copyPlannerMarkdown() {
  const content = document.querySelector('.markdown-content') ? document.querySelector('.markdown-content').innerText : '';
  navigator.clipboard.writeText(content).then(() => {
    alert('📋 마크다운 텍스트가 클립보드에 복사되었습니다!');
  });
}

function printPlanner() {
  window.print();
}

// ==========================================
// 4. 타이머 & 체크리스트 상태 연동
// ==========================================
function startTimer() {
  state.timer.isRunning = true;
  state.timer.isPaused = false;

  // [중요] 공부 시작 시 체크박스 비활성화 해제
  setCheckboxesDisabled(false);
  document.getElementById('btn-start-timer').innerText = "공부 중...";

  state.timer.intervalId = setInterval(() => {
    if (state.timer.remainingSeconds > 0) {
      state.timer.remainingSeconds--;
      updateTimerDisplay();
    } else {
      completeTimerSession();
    }
  }, 1000);
}

function pauseTimer() {
  state.timer.isRunning = false;
  state.timer.isPaused = true;
  clearInterval(state.timer.intervalId);

  // [중요] 쉬는 시간/일시정지 중 체크박스 잠금 (비활성화)
  setCheckboxesDisabled(true);
  document.getElementById('btn-start-timer').innerText = "공부 재개";
}

function setCheckboxesDisabled(disabled) {
  const checkboxes = document.querySelectorAll('.todo-checkbox');
  checkboxes.forEach(cb => {
    cb.disabled = disabled;
  });
}

// 조기 종료 및 비율 계산 벨 정산
function finishEarly() {
  clearInterval(state.timer.intervalId);

  const elapsedSeconds = state.timer.durationSeconds - state.timer.remainingSeconds;
  const ratio = elapsedSeconds / state.timer.durationSeconds;
  const maxBells = 25; // 최대 보상 벨

  const earnedBells = Math.floor(maxBells * ratio);
  state.user.bells += earnedBells;
  localStorage.setItem('study_bells', state.user.bells);

  alert(`조기 종료되었습니다.\n진행 비율: ${Math.round(ratio * 100)}%\n획득 벨: 🔔 ${earnedBells}벨`);
  document.getElementById('user-bell-count').innerText = `🔔 ${state.user.bells} 벨`;

  resetTimer();
}

function completeTimerSession() {
  clearInterval(state.timer.intervalId);
  const maxBells = 25;
  state.user.bells += maxBells;
  localStorage.setItem('study_bells', state.user.bells);
  document.getElementById('user-bell-count').innerText = `🔔 ${state.user.bells} 벨`;

  alert(`🎉 목표 25분 공부 완료!\n🔔 +${maxBells}벨을 획득하셨습니다!`);
  resetTimer();
}

function resetTimer() {
  state.timer.isRunning = false;
  state.timer.isPaused = false;
  state.timer.remainingSeconds = state.timer.durationSeconds;
  setCheckboxesDisabled(true); // 초기 잠금 상태 전환
  document.getElementById('btn-start-timer').innerText = "공부 시작";
  updateTimerDisplay();
}

function updateTimerDisplay() {
  const timerDisplayEl = document.getElementById('timer-display');
  if (!timerDisplayEl) return;
  const m = String(Math.floor(state.timer.remainingSeconds / 60)).padStart(2, '0');
  const s = String(state.timer.remainingSeconds % 60).padStart(2, '0');
  timerDisplayEl.innerText = `${m}:${s}`;
}
