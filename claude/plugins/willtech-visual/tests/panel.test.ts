import { expect, mock, test } from 'claude-code/testing'
import { PNG } from '../hooks/assets.js'

const PANE = {
  plugin: 'willtech-visual',
  component: 'Pane',
  requestId: 'willtech-team',
  viewport: { columns: 100, rows: 40 },
  props: {
    title: 'WillTech · Equipe',
    isFocused: true,
    bodyColumns: 80,
    placement: 'inline',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const NAMES = ['General', 'Explorador', 'Pesquisador', 'Visual', 'Executor', 'Testador', 'Revisor']

const info = (over: Record<string, unknown> = {}) => ({
  id: 'a1',
  description: 'explorar codigo',
  type: 'willtech-explorador',
  status: 'running',
  kind: 'local_agent',
  taskStatus: 'running',
  ...over,
})

function stubs(on: any, agents: unknown[] = []) {
  on('session.start', () => ({ cwd: '/work' }))
  on('session.end', () => ({ sessionId: 's1' }))
  on('command.register', () => ({ value: undefined }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('agent.list', () => ({ value: agents }))
  on('turn.start', (_$: unknown, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('agent.spawn', () => ({ agentId: 'a1' }))
}

test('o pane desenha os sete mascotes com estados reais nas duas superficies', async ($, on) => {
  stubs(on, [
    info(),
    info({ id: 'a2', type: 'willtech-executor', status: 'completed', taskStatus: 'completed' }),
    info({ id: 'a3', type: 'willtech-revisor', status: 'killed', taskStatus: 'killed' }),
  ])
  mock.clock(on)
  await $.session.start({ surface: 'desktop', isInteractive: true, cwd: '/work' })
  await $.command.run({ command: 'willtech-team', args: '' })

  for (const surface of ['desktop', 'terminal'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    for (const name of NAMES) {
      expect(await ui.find({ type: 'Text', text: name })).toBeDefined()
    }
    expect(await ui.find({ type: 'Text', text: 'Explorando código' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Concluído' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Interrompido' })).toBeDefined()
    if (surface === 'desktop') {
      expect(await ui.find({ type: 'Svg' })).toBeDefined()
    } else {
      expect(await ui.find({ type: 'Image', key: 'wt-img-willtech-general' })).toBeDefined()
    }
    await ui.unmount()
  }
})

test('eventos reais movem estados e a animacao terminal agenda quadros via blit', async ($, on) => {
  const blits: { key: string; png: string }[] = []
  stubs(on, [])
  on('ui.blit', (_$: unknown, e: any) => {
    blits.push({ key: e.key, png: e.source.png })
    return { value: undefined }
  })
  const clock = mock.clock(on)
  await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })
  await $.command.run({ command: 'willtech-team', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  const frames = () => blits.filter((b) => b.key === 'wt-img-willtech-general' && b.png !== PNG['willtech-general']).length
  const flush = () => new Promise((resolve) => setTimeout(resolve, 0))
  const must = (found: unknown, label: string) => { if (!found) throw new Error('MISSING ' + label) }

  await $.turn.start({ turnId: 't1' })
  await flush()
  must(await ui.find({ type: 'Text', text: 'Coordenando' }), 'Coordenando')
  await clock.advance(480)
  expect(frames()).toBeGreaterThan(0)

  await ui.press({ key: 'wt-motion' })
  await flush()
  await clock.advance(960)
  const afterPause = frames()
  await clock.advance(960)
  expect(frames()).toBe(afterPause)
  const pauseButton = await ui.find({ key: 'wt-motion' })
  must(JSON.stringify(pauseButton).includes('Ativar animações'), 'Ativar animacoes')

  await $.turn.complete({ turnId: 't1', answer: '', durationMs: 1, isAborted: false, usage: null })
  await flush()
  must(await ui.find({ type: 'Text', text: 'Concluído' }), 'Concluido')
  await clock.advance(960)
  expect(frames()).toBe(afterPause)

  await $.session.end({ sessionId: 's1' })
  await clock.advance(960)
  expect(frames()).toBe(afterPause)
  await ui.unmount()
})

test('no desktop a animacao SMIL liga e desliga com o estado e a pausa', async ($, on) => {
  stubs(on, [])
  mock.clock(on)
  await $.session.start({ surface: 'desktop', isInteractive: true, cwd: '/work' })
  await $.command.run({ command: 'willtech-team', args: '' })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })

  await $.turn.start({ turnId: 't1' })
  const working = await ui.find({ type: 'Svg' })
  expect(String(working?.props?.source)).toContain('animateTransform')

  await ui.press({ key: 'wt-motion' })
  const paused = await ui.find({ type: 'Svg' })
  expect(String(paused?.props?.source)).not.toContain('animateTransform')

  await $.turn.complete({ turnId: 't1', answer: '', durationMs: 1, isAborted: true, usage: null })
  expect(await ui.find({ type: 'Text', text: 'Interrompido' })).toBeDefined()
  const done = await ui.find({ type: 'Svg' })
  expect(String(done?.props?.source)).not.toContain('animateTransform')
  await ui.unmount()
})