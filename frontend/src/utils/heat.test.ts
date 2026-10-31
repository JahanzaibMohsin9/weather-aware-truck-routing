import { describe, expect, it } from 'vitest'
import { scalePosition } from './heat'

const WIND = [25, 35, 45, 55]

describe('scalePosition', () => {
  it('is linear between band starts', () => {
    expect(scalePosition(0, WIND)).toBe(0)
    expect(scalePosition(12.5, WIND)).toBeCloseTo(0.5)
    expect(scalePosition(30, WIND)).toBeCloseTo(1.5)
    expect(scalePosition(50, WIND)).toBeCloseTo(3.5)
  })

  it('puts each band start at a whole number, matching the levels', () => {
    expect(scalePosition(25, WIND)).toBe(1)
    expect(scalePosition(35, WIND)).toBe(2)
    expect(scalePosition(45, WIND)).toBe(3)
  })

  it('caps at 4 from the No Travel threshold up', () => {
    expect(scalePosition(55, WIND)).toBe(4)
    expect(scalePosition(90, WIND)).toBe(4)
  })

  it('works for uneven scales such as rain', () => {
    expect(scalePosition(0.375, [0.1, 0.25, 0.5, 1.0])).toBeCloseTo(2.5)
  })
})
