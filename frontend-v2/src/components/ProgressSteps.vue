<template>
  <el-steps :active="current" finish-status="success" align-center>
    <el-step title="上传" />
    <el-step title="匹配" />
    <el-step title="分析" />
    <el-step title="完成" />
  </el-steps>
</template>

<script setup>
defineProps({
  current: { type: Number, default: 0 }
})
</script>
