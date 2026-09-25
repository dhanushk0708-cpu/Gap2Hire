// Focused test for Gap2Hire frontend router & interview-live dispatching
const fs = require('fs');
const path = require('path');

// Setup minimal browser-like globals
global.window = global;
global.document = {
    getElementById: (id) => {
        if (!global.elements[id]) {
            global.elements[id] = {
                id,
                innerHTML: '',
                style: {},
                classList: {
                    add: () => {},
                    remove: () => {},
                },
                querySelector: () => null,
                querySelectorAll: () => [],
                addEventListener: () => {},
            };
        }
        return global.elements[id];
    },
    querySelectorAll: () => [],
};
global.elements = {};
global.localStorage = {
    getItem: (k) => 'test-token',
    setItem: () => {},
    removeItem: () => {},
};
global.window.location = {
    hash: '',
};

let eventListeners = {};
global.window.addEventListener = (event, fn) => {
    eventListeners[event] = fn;
};

// Load api.js, state.js, router.js, interview_live.js, candidate_detail.js
const apiCode = fs.readFileSync(path.join(__dirname, '../app/static/js/api.js'), 'utf8');
const stateCode = fs.readFileSync(path.join(__dirname, '../app/static/js/state.js'), 'utf8');
const routerCode = fs.readFileSync(path.join(__dirname, '../app/static/js/router.js'), 'utf8');
const liveCode = fs.readFileSync(path.join(__dirname, '../app/static/js/views/interview_live.js'), 'utf8');
const candDetailCode = fs.readFileSync(path.join(__dirname, '../app/static/js/views/candidate_detail.js'), 'utf8');

eval(apiCode);
eval(stateCode);
eval(liveCode);
eval(candDetailCode);
eval(routerCode);

router.init();

console.log("--- 1. Testing parseHash with #interview-live?applicationId=app-123&jobId=job-456 ---");
window.location.hash = '#interview-live?applicationId=app-123&jobId=job-456';
const parsed = router.parseHash();
console.log("Parsed result:", parsed);
if (parsed.path !== 'interview-live') throw new Error(`Expected path 'interview-live', got '${parsed.path}'`);
if (parsed.params.applicationId !== 'app-123') throw new Error(`Expected applicationId 'app-123', got '${parsed.params.applicationId}'`);
if (parsed.params.jobId !== 'job-456') throw new Error(`Expected jobId 'job-456', got '${parsed.params.jobId}'`);
console.log("[PASSED] parseHash correctly extracted route and params!");

console.log("\n--- 2. Testing router dispatch when hashchange occurs ---");
let renderedWith = null;
window.interviewLiveView.render = (container, params) => {
    renderedWith = params;
    container.innerHTML = `<div id="live-screen">Live interview for ${params.applicationId}</div>`;
};

// Simulate hashchange event
eventListeners['hashchange']();
const mainView = document.getElementById('main-view');
console.log("Rendered with params:", renderedWith);
console.log("mainView innerHTML:", mainView.innerHTML);

if (!renderedWith) throw new Error("interviewLiveView.render was not called on hashchange!");
if (renderedWith.applicationId !== 'app-123') throw new Error("interviewLiveView did not receive applicationId!");
if (!mainView.innerHTML.includes('Live interview for app-123')) throw new Error("main-view was not updated!");
console.log("[PASSED] Hashchange successfully updated main-view to interview live screen!");

console.log("\n--- 3. Testing candidateDetailView.startInterviewFlow() ---");
candidateDetailView.currentAppId = 'app-789';
candidateDetailView.screeningReport = { job_id: 'job-999' };
candidateDetailView.startInterviewFlow();

console.log("New window.location.hash:", window.location.hash);
if (window.location.hash !== '#interview-live?applicationId=app-789&jobId=job-999') {
    throw new Error(`Unexpected hash: ${window.location.hash}`);
}
eventListeners['hashchange']();
console.log("mainView innerHTML after startInterviewFlow:", mainView.innerHTML);
if (!mainView.innerHTML.includes('Live interview for app-789')) {
    throw new Error("startInterviewFlow did not update main-view!");
}
console.log("[PASSED] Candidate detail button navigated and rendered interview-live!");

console.log("\n--- 4. Testing return to candidate-detail route ---");
let candRenderedId = null;
window.candidateDetailView.render = (id) => {
    candRenderedId = id;
    mainView.innerHTML = `<div id="cand-detail-screen">Candidate Detail for ${id}</div>`;
};
window.location.hash = '#candidate-detail?id=app-789';
eventListeners['hashchange']();
console.log("mainView innerHTML after returning to candidate detail:", mainView.innerHTML);
if (!mainView.innerHTML.includes('Candidate Detail for app-789')) {
    throw new Error("Candidate detail route failed to render!");
}
console.log("[PASSED] Candidate detail route preserved and verified!");

console.log("\n[ALL FRONTEND ROUTER TESTS PASSED 100%]");
