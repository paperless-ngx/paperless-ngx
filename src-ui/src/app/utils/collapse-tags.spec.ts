import { Tag } from '../data/tag'
import { collapseImpliedAncestors, getTagAncestors } from './collapse-tags'

const tags: Tag[] = [
  { id: 1, name: 'Finance' },
  { id: 2, name: 'Account', parent: 1 },
  { id: 3, name: 'Mortgage', parent: 2 },
  { id: 4, name: 'Taxes', parent: 1 },
  { id: 5, name: 'Inbox' },
]
const tagsById = new Map(tags.map((t) => [t.id, t]))

describe('collapseImpliedAncestors', () => {
  it('drops ancestors that are implied by a descendant in the list', () => {
    expect(collapseImpliedAncestors([1, 2, 3, 4, 5], tagsById)).toEqual([
      3, 4, 5,
    ])
  })

  it('keeps a parent with none of its children present', () => {
    expect(collapseImpliedAncestors([1, 5], tagsById)).toEqual([1, 5])
  })

  it('keeps unknown (private) ids and handles empty input', () => {
    expect(collapseImpliedAncestors([99, 2], tagsById)).toEqual([99, 2])
    expect(collapseImpliedAncestors([], tagsById)).toEqual([])
    expect(collapseImpliedAncestors(null, tagsById)).toEqual([])
  })
})

describe('getTagAncestors', () => {
  it('returns ancestors root first', () => {
    expect(getTagAncestors(3, tagsById).map((t) => t.id)).toEqual([1, 2])
    expect(getTagAncestors(5, tagsById)).toEqual([])
  })

  it('stops at a parent that is not visible or forms a cycle', () => {
    const hidden = new Map<number, Tag>([[6, { id: 6, name: 'x', parent: 99 }]])
    expect(getTagAncestors(6, hidden)).toEqual([])

    const cyclic = new Map<number, Tag>([
      [7, { id: 7, name: 'a', parent: 8 }],
      [8, { id: 8, name: 'b', parent: 7 }],
    ])
    expect(getTagAncestors(7, cyclic).map((t) => t.id)).toEqual([7, 8])
  })
})
