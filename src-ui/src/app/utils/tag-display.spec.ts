import { Tag } from '../data/tag'
import {
  collapseImpliedAncestors,
  getTagAncestors,
  partitionTags,
} from './tag-display'

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

describe('partitionTags', () => {
  it('splits ids into visible and hidden, keeping order', () => {
    expect(partitionTags([5, 98, 4, 99], tagsById, true)).toEqual({
      visible: [5, 4],
      hidden: [98, 99],
    })
    expect(partitionTags(null, tagsById, true)).toEqual({
      visible: [],
      hidden: [],
    })
  })

  it('drops implied ancestors only when showing hierarchy', () => {
    expect(partitionTags([1, 2, 3], tagsById, true).visible).toEqual([3])
    expect(partitionTags([1, 2, 3], tagsById, false).visible).toEqual([1, 2, 3])
  })

  it('drops a hidden ancestor of a visible tag only when showing hierarchy', () => {
    const withHiddenParent = new Map(tagsById)
    withHiddenParent.set(6, { id: 6, name: 'Child', parent: 98 })
    expect(partitionTags([6, 98, 99], withHiddenParent, true)).toEqual({
      visible: [6],
      hidden: [99],
    })
    expect(partitionTags([6, 98, 99], withHiddenParent, false).hidden).toEqual([
      98, 99,
    ])
  })
})
