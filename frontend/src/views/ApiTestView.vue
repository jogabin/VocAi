<script setup>
// 기존 FastAPI 연동 테스트 화면 (이전 App.vue 내용)
import HelloPanel from '../components/WellcomPanel.vue'
import UserList from '../components/UserList.vue'
</script>

<template>
  <main class="page api-test">
    <div class="card card-body">
      <h2 style="margin-bottom: 16px">FastAPI 연동 테스트</h2>
      <HelloPanel />
      <UserList />
    </div>
  </main>
</template>

<style>
.api-test section { margin-bottom: 32px; }
.api-test h2 { font-size: 18px; }
.api-test .row { display: flex; gap: 8px; margin: 8px 0; align-items: center; }
.api-test button { padding: 6px 12px; cursor: pointer; }
.api-test table { width: 100%; border-collapse: collapse; margin-top: 8px; }
.api-test th, .api-test td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
.api-test .ok { color: #0a7d2c; }
.api-test .err { color: #c62828; }
</style>
