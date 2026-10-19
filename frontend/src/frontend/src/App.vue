<template>
  <el-container class="app-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon :size="20"><DataAnalysis /></el-icon>
        <span>BOM风险链路引擎</span>
      </div>
      <el-menu
        :default-active="activeRoute"
        background-color="#1d1e2c"
        text-color="#a0a0b8"
        active-text-color="#409eff"
        router
        class="sidebar-menu"
      >
        <!-- 驾驶舱 -->
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>风险链路驾驶舱</span>
        </el-menu-item>

        <!-- BOM分析 -->
        <el-sub-menu index="bom-center">
          <template #title>
            <el-icon><Folder /></el-icon>
            <span>BOM分析</span>
          </template>
          <el-menu-item index="/projects">项目列表</el-menu-item>
          <el-menu-item index="/analyze">上传分析</el-menu-item>
          <el-menu-item index="/dashboard">风险仪表盘</el-menu-item>
        </el-sub-menu>

        <!-- 项目评审 -->
        <el-menu-item index="/project-review">
          <el-icon><Document /></el-icon>
          <span>项目评审管理</span>
        </el-menu-item>

        <!-- 交付监控 -->
        <el-menu-item index="/delivery-risk">
          <el-icon><Timer /></el-icon>
          <span>交付风险预警</span>
        </el-menu-item>

        <!-- 行情中心 -->
        <el-sub-menu index="market-center">
          <template #title>
            <el-icon><Bell /></el-icon>
            <span>行情中心</span>
          </template>
          <el-menu-item index="/events">市场事件</el-menu-item>
          <el-menu-item index="/market-inbox">行情收件箱</el-menu-item>
          <el-menu-item index="/market-trends">趋势验证</el-menu-item>
          <el-menu-item index="/watch">情报监控</el-menu-item>
        </el-sub-menu>

        <!-- 物料管理 -->
        <el-sub-menu index="material-center">
          <template #title>
            <el-icon><Coin /></el-icon>
            <span>物料管理</span>
          </template>
          <el-menu-item index="/materials">材料链路库</el-menu-item>
          <el-menu-item index="/preferred-library">策略与优选库</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <div class="sidebar-footer">
        <div class="status-dot" :class="{ online: backendOnline }"></div>
        <span class="version">v4.1</span>
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
const activeRoute = computed(() => route.path)
const backendOnline = ref(false)

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/health')
    backendOnline.value = data.status === 'ok'
  } catch {
    backendOnline.value = false
  }
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

.app-container {
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.sidebar {
  background: #1d1e2c;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 18px 20px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid #2a2b3d;
}

.sidebar-menu {
  border-right: none;
  flex: 1;
}

.sidebar-menu .el-menu-item,
.sidebar-menu .el-sub-menu__title {
  height: 48px;
  line-height: 48px;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #2a2b3d;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f56c6c;
}

.status-dot.online {
  background: #67c23a;
}

.version {
  color: #606266;
  font-size: 12px;
  margin-left: auto;
}

.main-content {
  background: #f5f7fa;
  padding: 24px;
  overflow-y: auto;
}
</style>
