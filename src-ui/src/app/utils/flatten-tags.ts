import { Tag } from '../data/tag'

export function flattenTags(all: Tag[]): Tag[] {
  const map = new Map<number, Tag>(
    all.map((t) => [t.id, { ...t, children: [] }])
  )
  // rebuild children
  for (const t of map.values()) {
    if (t.parent) {
      const p = map.get(t.parent)
      p?.children.push(t)
    }
  }
  const roots = Array.from(map.values()).filter((t) => !t.parent)
  const sortByName = (a: Tag, b: Tag) =>
    a.name.localeCompare(b.name, undefined, {
      sensitivity: 'base',
      numeric: true,
    })
  const ordered: Tag[] = []
  let idx = 0
  const walk = (node: Tag, depth: number) => {
    node.depth = depth
    node.orderIndex = idx++
    ordered.push(node)
    if (node.children?.length) {
      for (const child of [...node.children].sort(sortByName)) {
        walk(child, depth + 1)
      }
    }
  }
  roots.sort(sortByName)
  roots.forEach((r) => walk(r, 0))
  return ordered
}
