import type { Tag } from '../data/tag'
import { flattenTags } from './flatten-tags'

describe('flattenTags', () => {
  it('returns empty array for empty input', () => {
    expect(flattenTags([])).toEqual([])
  })

  it('orders roots and children by name (case-insensitive, numeric) and sets depth/orderIndex', () => {
    const input: Tag[] = [
      { id: 11, name: 'A-root' },
      { id: 10, name: 'B-root' },
      { id: 101, name: 'Child 10', parent: 11 },
      { id: 102, name: 'child 2', parent: 11 },
      { id: 201, name: 'beta', parent: 10 },
      { id: 202, name: 'Alpha', parent: 10 },
      { id: 103, name: 'Sub 1', parent: 102 },
    ]

    const flat = flattenTags(input)

    const names = flat.map((t) => t.name)
    expect(names).toEqual([
      'A-root',
      'child 2',
      'Sub 1',
      'Child 10',
      'B-root',
      'Alpha',
      'beta',
    ])

    expect(flat.map((t) => t.depth)).toEqual([0, 1, 2, 1, 0, 1, 1])
    expect(flat.map((t) => t.orderIndex)).toEqual([0, 1, 2, 3, 4, 5, 6])

    // Children are rebuilt
    const aRoot = flat.find((t) => t.name === 'A-root')
    expect(new Set(aRoot.children?.map((c) => c.name))).toEqual(
      new Set(['child 2', 'Child 10'])
    )

    const bRoot = flat.find((t) => t.name === 'B-root')
    expect(new Set(bRoot.children?.map((c) => c.name))).toEqual(
      new Set(['Alpha', 'beta'])
    )

    const child2 = flat.find((t) => t.name === 'child 2')
    expect(new Set(child2.children?.map((c) => c.name))).toEqual(
      new Set(['Sub 1'])
    )
  })

  it('excludes orphaned nodes (with missing parent)', () => {
    const input: Tag[] = [
      { id: 1, name: 'Root' },
      { id: 2, name: 'Child', parent: 1 },
      { id: 3, name: 'Orphan', parent: 999 }, // missing parent
    ]

    const flat = flattenTags(input)
    expect(flat.map((t) => t.name)).toEqual(['Root', 'Child'])
  })
})
