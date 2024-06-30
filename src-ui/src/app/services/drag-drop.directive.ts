import { Directive, HostListener } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { FoldersService } from './rest/folders.service';

@Directive({
  selector: '[pngxDragDrop]'
})
export class DragDropDirective {
  constructor(private foldersService: FoldersService) { }

  @HostListener('dragover', ['$event'])
  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    console.log('Drag over event triggered');
  }

  @HostListener('drop', ['$event'])
  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    console.log('Drop event triggered');
    const folderId = (event.target as HTMLElement)?.getAttribute('id-khai');
    if (folderId) {
      console.log(`Dropped into folder with id-khai="${folderId}"`);

      const files = event.dataTransfer?.files;
      if (files && files.length > 0) {
        Array.from(files).forEach(file => this.uploadDocumentToFolder(file, Number(folderId)));
      } else {
        console.error('No files found in drop event');
      }
    }
  }

  uploadDocumentToFolder(file: File, folderId: number) {
    const formData = new FormData();
    formData.append('document', file);
    formData.append('folder', folderId.toString());

    this.foldersService.uploadDocument(formData).subscribe(
      response => {
        console.log('Document uploaded successfully', response);
      },
      error => {
        console.error('Error uploading document', error);
      }
    );
  }
}