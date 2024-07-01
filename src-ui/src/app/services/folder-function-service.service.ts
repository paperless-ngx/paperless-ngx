import { Injectable } from '@angular/core';
import { FoldersService } from './rest/folders.service';
import { Results } from '../data/folders';

@Injectable({
  providedIn: 'root'
})
export class FolderFunctionServiceService {

  constructor(private folderService: FoldersService) { }

  // Phương thức xóa nhiều phần tử
  deleteMultipleItems(event: MouseEvent, results: Results[], loadFolders: () => void, loadFolderContents: (folderId: number) => void, currentFolderId: number): void {
    const target = event.currentTarget as HTMLElement;
    const add2Attribute = target.getAttribute('add2');
    if (add2Attribute) {
      const idsToDelete = add2Attribute.split(',').map(id => parseInt(id.trim(), 10));

      this.folderService.bulkDeleteFolders(idsToDelete).subscribe(
        () => {
          results = results.filter(result => !idsToDelete.includes(result.id));
          console.log(`IDs ${idsToDelete.join(', ')} have been deleted.`);
          loadFolders();
          loadFolderContents(currentFolderId);
        },
        error => {
          console.error('Error deleting multiple items:', error);
        }
      );
    }
  }

  // Phương thức xóa một phần tử
  deleteItem(event: MouseEvent, results: Results[], loadFolders: () => void, loadFolderContents: (folderId: number) => void, currentFolderId: number): void {
    const target = event.currentTarget as HTMLElement;
    const addAttribute = target.getAttribute('add');
    if (addAttribute) {
      const idToDelete = parseInt(addAttribute, 10);

      this.folderService.deleteFolder(idToDelete).subscribe(
        () => {
          results = results.filter(result => result.id !== idToDelete);
          console.log(`ID ${idToDelete} has been deleted.`);
          loadFolders();
          loadFolderContents(currentFolderId);
        },
        error => {
          console.error('Error deleting item:', error);
        }
      );
    }
  }
  deleteFile(event: Event): void {
    const target = event.target as HTMLElement;
    const idAttr = target.closest('li')?.getAttribute('chua');
    if (idAttr) {
      const id = parseInt(idAttr, 10);
      if (!isNaN(id)) {
        this.folderService.deleteFileById(id).subscribe({
          next: () => {
            console.log(`File with ID ${id} has been deleted.`);
            // Optionally, you can handle further actions here
          },
          error: (err) => {
            console.error(`Error deleting file with ID ${id}:`, err);
          }
        });
      } else {
        console.error('Invalid ID');
      }
    } else {
      console.error('ID not found');
    }
  }
  

}
