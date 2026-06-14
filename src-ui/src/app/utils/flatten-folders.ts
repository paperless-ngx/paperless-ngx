import { Folder } from '../data/folder'

export function flattenFolders(
  folders: Folder[],
  depth: number = 0,
  orderIndex: { value: number } = { value: 0 }
): Folder[] {
  return folders.flatMap((folder) => {
    const flattenedFolder: Folder = {
      ...folder,
      depth,
      full_path: folder.full_path ?? folder.name,
      orderIndex: orderIndex.value++,
    }

    return [
      flattenedFolder,
      ...flattenFolders(folder.children ?? [], depth + 1, orderIndex),
    ]
  })
}
