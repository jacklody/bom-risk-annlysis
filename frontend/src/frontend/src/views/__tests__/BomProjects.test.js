import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import BomProjects from '../BomProjects.vue'
import * as bomApi from '../../api/bom'

vi.mock('../../api/bom', () => ({
  listBomProjects: vi.fn()
}))

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push })
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() }
}))

let currentRows = []

const stubs = {
  'el-card': { template: '<section><slot name="header" /><slot /></section>' },
  'el-button': {
    props: ['loading', 'disabled', 'type', 'size', 'link'],
    emits: ['click'],
    template: '<button v-bind="$attrs" :disabled="loading || disabled" @click="$emit(\'click\')"><slot /></button>'
  },
  'el-tag': { props: ['type'], template: '<span><slot /></span>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}</div>' },
  'el-table': {
    inheritAttrs: false,
    props: ['data', 'stripe', 'rowKey', 'class'],
    setup(props, { slots }) {
      return () => {
        currentRows = props.data || []
        return slots.default?.()
      }
    }
  },
  'el-table-column': {
    inheritAttrs: false,
    props: ['prop', 'label'],
    setup(props, { slots }) {
      return () => currentRows.map(row => slots.default ? slots.default({ row }) : row[props.prop])
    }
  }
}

describe('BomProjects', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    push.mockReset()
    currentRows = []
  })

  it('加载并展示历史BOM项目列表，可进入项目详情', async () => {
    bomApi.listBomProjects.mockResolvedValue({
      data: {
        projects: [
          {
            id: 7,
            project_name: '历史BOM-A',
            filename: 'history-a.xlsx',
            status: 'active',
            total_items: 12,
            items_red: 2,
            items_yellow: 3,
            items_green: 7,
            items_gray: 0,
            has_new_risks: true,
            last_analysis_at: '2026-06-28T09:55:31'
          }
        ]
      }
    })

    const wrapper = mount(BomProjects, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(bomApi.listBomProjects).toHaveBeenCalled()
    expect(wrapper.text()).toContain('历史BOM-A')
    expect(wrapper.text()).toContain('history-a.xlsx')
    expect(wrapper.text()).toContain('共 12 项')
    expect(wrapper.text()).toContain('高风险 2')
    expect(wrapper.text()).toContain('新增风险')

    await wrapper.find('[data-testid="open-project-7"]').trigger('click')
    expect(push).toHaveBeenCalledWith('/projects/7')
  })
})
