import { Component } from '@angular/core';
import { FoldersService } from 'src/app/services/rest/folders.service';

@Component({
  selector: 'pngx-viewall-forder',
  standalone: true,
  imports: [],
  templateUrl: './viewall-forder.component.html',
  styleUrl: './viewall-forder.component.scss'
})
export class ViewallForderComponent {
  folders: any[] = [];
  documents: any[] = [];

  constructor(private foldersService: FoldersService) { }

  ngOnInit(): void {
    this.foldersService.getFoldersAndDocuments().subscribe(data => {
      this.folders = data.folders;
      this.documents = data.documents;
    });
  }
  calculateFileSize(checksum: string): string {
    return checksum.length.toString() + ' bytes';
  }
}
