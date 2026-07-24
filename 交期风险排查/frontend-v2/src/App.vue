<template>
  <el-container class="app-container">
    <el-aside width="200px" class="sidebar">
      <div class="logo">
        <el-icon :size="20"><DataAnalysis /></el-icon>
        <span>行情风险引擎</span>
      </div>
      <el-menu
        :default-active="activeRoute"
        background-color="#1d1e2c"
        text-color="#a0a0b8"
        active-text-color="#409eff"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><Upload /></el-icon>
          <span>上传分析</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><Folder /></el-icon>
          <span>BOM项目</span>
        </el-menu-item>
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>风险仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/material-chain" class="menu-highlight">
          <el-icon><Connection /></el-icon>
          <span>上游材料链路</span>
        </el-menu-item>
        <el-menu-item index="/intelligence">
          <el-icon><Bell /></el-icon>
          <span>行情情报中心</span>
        </el-menu-item>
        <el-menu-item index="/preferred-library">
          <el-icon><Star /></el-icon>
          <span>优选库治理</span>
        </el-menu-item>
        <el-menu-item index="/materials">
          <el-icon><Coin /></el-icon>
          <span>原材料追踪</span>
        </el-menu-item>
        <el-menu-item index="/data-sources">
          <el-icon><Connection /></el-icon>
          <span>数据源状态</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="status-dot" :class="{ online: backendOnline }"></div>
        <span class="version">v0.3.0</span>
      </div>
    </el-aside>

    <el-main class="main-content">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const backendOnline = ref(false)

const activeRoute = computed(() => {
  const path = route.path
  if (path.startsWith('/intelligence')) return '/intelligence'
  if (['/events', '/market-trends', '/market-inbox', '/watch'].includes(path)) return '/intelligence'
  if (path.startsWith('/material-chain')) return '/material-chain'
  return path
})

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/health')
    backendOnline.value = data.status === 'ok'
  } catch { backendOnline.value = false }
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
.app-container { height: 100vh; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
.sidebar { background: #1d1e2c; display: flex; flex-direction: column; overflow: hidden; }
.logo { display: flex; align-items: center; gap: 8px; padding: 18px 20px; color: #fff; font-size: 15px; font-weight: 600; border-bottom: 1px solid #2a2b3d; }
.sidebar-menu { border-right: none; flex: 1; }
.sidebar-menu .el-menu-item { height: 48px; line-height: 48px; }
.sidebar-menu .menu-highlight { border-left: 3px solid #67c23a; }
.sidebar-footer { display: flex; align-items: center; gap: 8px; padding: 12px 20px; border-top: 1px solid #2a2b3d; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #f56c6c; }
.status-dot.online { background: #67c23a; }
.version { color: #606266; font-size: 12px; margin-left: auto; }
.main-content { background: #f5f7fa; padding: 24px; overflow-y: auto; }
</style>
