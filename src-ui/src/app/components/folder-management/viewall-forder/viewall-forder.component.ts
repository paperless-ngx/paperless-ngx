import { Component, OnInit } from '@angular/core';
import { FoldersService } from 'src/app/services/rest/folders.service';
import { Document, Folders } from 'src/app/data/folders'; 

@Component({
  selector: 'app-view-all-folder',
  templateUrl: './viewall-forder.component.html',
  styleUrls: ['./viewall-forder.component.scss']
})
export class ViewAllFolderComponent implements OnInit {
  folders: Folders[] = [];
  documents: Document[] = [];

  constructor(private foldersService: FoldersService) {}

  ngOnInit(): void {
    this.foldersService.getFoldersAndDocuments().subscribe({
      next: data => {
        this.folders = data.folders;
        this.documents = data.documents;
        this.initializeFolders();
        this.initializeDocuments();
        this.addEventListeners();
      },
      error: error => {
        console.error('Error fetching data:', error);
        // Xử lý lỗi theo yêu cầu của bạn
      }
    });
  }

  initializeFolders(): void {
    const foldersContainer = document.getElementById('folders-container');
    if (foldersContainer) {
      foldersContainer.innerHTML = '';

      const createFolders = (parentId: number | null, parentDiv: HTMLElement | null) => {
        this.folders.forEach(folder => {
          if (folder.parent_folder_id === parentId) {
            const folderHTML = this.createFolderHTML(folder, parentDiv);
            createFolders(folder.id, folderHTML.querySelector('.children-container') as HTMLElement);
          }
        });
      };

      this.folders.forEach(folder => {
        if (folder.parent_folder_id === null) {
          const folderHTML = this.createFolderHTML(folder);
          foldersContainer.appendChild(folderHTML);
          this.documents.forEach(doc => {
            if (doc.folder_id === folder.id) {
              const documentHTML = this.createDocumentHTML(doc);
              folderHTML.querySelector('.children-container')?.appendChild(documentHTML);
            }
          });
          createFolders(folder.id, folderHTML.querySelector('.children-container') as HTMLElement);
        }
      });
    }
  }

  initializeDocuments(): void {
    const documentsContainer = document.getElementById('documents-container');
    const foldersContainer = document.getElementById('folders-container');

    if (documentsContainer && foldersContainer) {
      documentsContainer.innerHTML = '';

      const addedDocumentFilenames = new Set<string>();

      this.documents.forEach(doc => {
        if (!addedDocumentFilenames.has(doc.filename)) {
          const folder = this.findFolderById(doc.folder_id);
          if (folder && folder.id === 71) {
            const folderDiv = this.findFolderDiv(folder.id);
            if (folderDiv) {
              const documentsContainerInFolder = folderDiv.querySelector('.documents-container');
              if (documentsContainerInFolder) {
                if (!documentsContainerInFolder.querySelector(`.document[data-document-id="${doc.id}"]`)) {
                  const documentHTML = this.createDocumentHTML(doc);
                  documentsContainerInFolder.appendChild(documentHTML);
                  addedDocumentFilenames.add(doc.filename);
                }
              }
            }
          } else {
            if (!documentsContainer.querySelector(`.document[data-document-id="${doc.id}"]`)) {
              const documentHTML = this.createDocumentHTML(doc);
              documentsContainer.appendChild(documentHTML);
              addedDocumentFilenames.add(doc.filename);
            }
          }
        }
      });
    }
  }

  createFolderHTML(folder: Folders, parentDiv: HTMLElement | null = null): HTMLElement {
    const folderDiv = document.createElement('div');
    folderDiv.classList.add('folder');
    folderDiv.dataset.folderId = folder.id.toString();

    if (this.hasParentFolder(folder.id)) {
      const keDiv = document.createElement('div');
      keDiv.classList.add('ke');
      folderDiv.appendChild(keDiv);
    }

    if (parentDiv) {
      parentDiv.appendChild(folderDiv);
      folderDiv.style.marginLeft = '0px';
    }

    const folderIcon = document.createElement('i');
    folderIcon.classList.add('fa', 'fa-solid', 'fa-chevron-right');
    const folderIconFolder = document.createElement('i');
    folderIconFolder.classList.add('fa', 'fa-solid', 'fa-folder');

    const folderName = document.createElement('p');
    folderName.textContent = folder.name;

    const folderHeader = document.createElement('div');
    folderHeader.classList.add('folder-cha');
    folderHeader.appendChild(folderIcon);
    folderHeader.appendChild(folderIconFolder);
    folderHeader.appendChild(folderName);

    folderDiv.appendChild(folderHeader);

    const childrenContainer = document.createElement('div');
    childrenContainer.classList.add('children-container');
    childrenContainer.style.display = 'none';
    folderDiv.appendChild(childrenContainer);

    return folderDiv;
  }

  createDocumentHTML(doc: Document): HTMLElement {
    const documentDiv = document.createElement('div');
    documentDiv.classList.add('document');
    documentDiv.dataset.documentId = doc.id.toString();

    const documentName = document.createElement('p');
    documentName.textContent = doc.filename;

    const documentContainer = document.createElement('div');
    documentContainer.classList.add('document-container');
    documentContainer.appendChild(documentName);

    documentDiv.appendChild(documentContainer);
    return documentDiv;
  }

  hasParentFolder(folderId: number): boolean {
    return this.folders.some(folder => folder.parent_folder_id === folderId);
  }

  findFolderById(folderId: number | null): Folders | undefined {
    return this.folders.find(folder => folder.id === folderId);
  }

  findFolderDiv(folderId: number): HTMLElement | null {
    const foldersContainer = document.getElementById('folders-container');
    return foldersContainer?.querySelector(`.folder[data-folder-id="${folderId}"]`) as HTMLElement;
  }

  addEventListeners(): void {
    document.addEventListener('DOMContentLoaded', () => {
      const folderLeft = document.getElementById('folderLeft');
      if (folderLeft) {
        const resizeHandle = folderLeft.querySelector('.resize-handle') as HTMLElement | null;
        if (resizeHandle) {
          let startX: number, startWidth: number;
    
          resizeHandle.addEventListener('mousedown', (event: MouseEvent) => {
            startX = event.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(folderLeft).width, 10);
    
            document.addEventListener('mousemove', resizeWidth);
            document.addEventListener('mouseup', stopResize);
          });
    
          const resizeWidth = (event: MouseEvent) => {
            const newWidth = startWidth + (event.clientX - startX);
            folderLeft.style.width = newWidth + 'px';
            const folderRight = document.querySelector('.folder-right') as HTMLElement | null;
            if (folderRight) {
              folderRight.style.width = `calc(100% - ${newWidth}px)`;
            }
          };
    
          const stopResize = () => {
            document.removeEventListener('mousemove', resizeWidth);
            document.removeEventListener('mouseup', stopResize);
          };
        }
      }

      // Handle folder open/close toggle
      const folderCha = document.querySelectorAll('.folder-cha');
      if (folderCha.length > 0) {
        folderCha.forEach(item => {
          let isOpen = false; // Track whether folder is open or closed
          const folderIcon = item.querySelector('.fa-folder');
          const chevronIcon = item.querySelector('.fa-chevron-right') as HTMLElement;
          const folder = item.closest('.folder');
          const ke = folder.querySelector('.ke');

          item.addEventListener('click', () => {
            if (isOpen) {
              const ke = folder.querySelector('.ke') as HTMLElement;
              ke.style.display = 'none'; // Hide .ke when closing the folder
              folderIcon.classList.remove('fa-folder-open' ) ;
              folderIcon.classList.add('fa-folder');
              chevronIcon.style.transform = ''; // Reset chevron rotation
            } else {
              const ke = folder.querySelector('.ke') as HTMLElement;
              ke.style.display = 'block'; // Show .ke when opening the folder
              folderIcon.classList.remove('fa-folder');
              folderIcon.classList.add('fa-folder-open');
              chevronIcon.style.transform = 'rotate(90deg)'; // Rotate chevron
            }

            isOpen = !isOpen; // Toggle isOpen state
          });
        });
      }
    });
  }
}
