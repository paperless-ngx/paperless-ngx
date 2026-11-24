import { Tag } from '../data/tag'

/**
 * Collapses implied ancestor tags from a list of tag IDs such that if a tag's
 * ancestor is also present in the list, the ancestor is removed. For example
 * [Finance, Account, Mortgage] -> [Mortgage]
 */
export function collapseImpliedAncestors(
  ids: number[],
  tagsById: Map<number, Tag>
): number[] {
  if (!ids?.length) return ids ?? []
  const present = new Set(ids)
  const implied = new Set<number>()
  for (const id of ids) {
    const seen = new Set<number>()
    let parentId = tagsById.get(id)?.parent
    while (parentId && !seen.has(parentId)) {
      seen.add(parentId)
      if (present.has(parentId)) implied.add(parentId)
      parentId = tagsById.get(parentId)?.parent
    }
  }
  return ids.filter((id) => !implied.has(id))
}

/**
 * Returns an array of ancestor tags for the given tag ID, starting from the
 * root and ending with the immediate parent.
 */
export function getTagAncestors(id: number, tagsById: Map<number, Tag>): Tag[] {
  const chain: Tag[] = []
  const seen = new Set<number>()
  let parentId = tagsById.get(id)?.parent
  while (parentId && !seen.has(parentId)) {
    seen.add(parentId)
    const parent = tagsById.get(parentId)
    if (!parent) break
    chain.unshift(parent)
    parentId = parent.parent
  }
  return chain
}
