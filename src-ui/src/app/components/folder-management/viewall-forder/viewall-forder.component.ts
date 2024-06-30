import { Component, OnInit, Renderer2, ElementRef,ViewChild } from '@angular/core';
import { FoldersService } from 'src/app/services/rest/folders.service';
import { Document, Folders, Results,SRC  } from 'src/app/data/folders';
import { PreventRightClickDirective } from 'src/app/services/prevent-right-click.directive';
import { ChangeDetectorRef } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http'; 
import { HttpClient } from '@angular/common/http';
import { environment } from 'src/environments/environment'
import { Directive, HostListener } from '@angular/core';
import { DragDropDirective } from 'src/app/services/drag-drop.directive';
import { Router } from '@angular/router';
@Component({
  selector: 'app-view-all-folder',
  templateUrl: './viewall-forder.component.html',
  styleUrls: ['./viewall-forder.component.scss']
})
export class ViewallForderComponent implements OnInit {
  protected baseUrl: string = environment.apiBaseUrl
  folders: Folders[] = [];
  documents: Document[] = [];
  results: Results[] = [];
  thesis: Document[] = [];
  filteredDocuments: Document[] = [];
  selectedFolderId: number | null = null;
  loggedFolderPath: string | null = null;
  folderName: string = '';
  parent_folder: number | null = null;
  folder: number | null = null;
  public renameFolderName: string = '';
  public renameFileName: string = '';
  private renameFolderId: number | null = null;
  private renameFileId: number | null = null;
  @ViewChild('cutElement') cutElement: ElementRef | undefined;
  @ViewChild('pasteElement') pasteElement: ElementRef | undefined;
  cutItemId: number | null = null;
  @ViewChild('cutElementf', { static: false }) cutElementf: ElementRef;
  @ViewChild('pasteElementf', { static: false }) pasteElementf: ElementRef;
  cutItemIdf: number | null = null;
  @ViewChild('folderRightContent') folderRightContent: ElementRef;
  uploadedDocuments: Document[] = [];
  addedStyleElement: HTMLStyleElement | null = null;
  @ViewChild('folderDropArea') folderDropAreaRef!: ElementRef;
  private rightClickedOnFolderDropArea: boolean = false;
  @ViewChild('folderDropArea') folderDropAreaRe!: ElementRef;




  

  constructor(
    private foldersService: FoldersService, 
    private renderer: Renderer2, 
    private elementRef: ElementRef,
    private cdr: ChangeDetectorRef,
    private http: HttpClient,
    private router: Router
  ) {}

 ngOnInit(): void {
  this.addGridStyles();
  this.loadFolders(); 
    this.foldersService.getFoldersAndDocuments().subscribe({
      next: (data: any) => {
        this.folders = data.folders;
        this.documents = data.documents;
        this.loadFolders();
        this.initializeFolders();
        this.initializeDocuments();
        this.addEventListeners();
        this.addEventListenerss();
      },
      error: error => {
        console.error('Error fetching data:', error);
      }
    });

    this.foldersService.getResults().subscribe({
      next: (data: any) => {
        this.results = data.results.filter(result => result.parent_folder !== null);
        this.initializeFolders();
      },
      error: error => {
        console.error('Error fetching results:', error);
      }
    });
    this.foldersService.getdocument().subscribe({
      next: (data: any) => {
        this.thesis = data.thesis.filter(document => document.folder !== null);
        this.initializeFolders();
      },
      error: error => {
        console.error('Error fetching documents:', error);
      }
    });    
    
  }
  navigateToDocument(id: number) {
    this.router.navigate(['/documents', id]);
  }
  loadFolderContents(folderId: number): void {
    this.foldersService.fetchfolderandDocuments(folderId).subscribe({
      next: (data: { documents: Document[], folders: Folders[] }) => {
        this.folders = data.folders;
        this.documents = data.documents;
        this.appendToTable(data.folders, data.documents, folderId);
        this.displayFolderPath(data.folders.find(folder => folder.id === folderId)?.path || '');
      },
      error: (error: HttpErrorResponse) => {
        console.error('Error fetching folder contents:', error);
      }
    });
  }
  
  
  loadFolderContentss(folderId: number): void {
    this.foldersService.fetchfolderandDocuments(folderId).subscribe({
      next: (data: { documents: Document[], folders: Folders[] }) => {
        this.appendToTable(data.folders, data.documents, folderId);
        this.loadFolders();
      },
      error: (error: HttpErrorResponse) => {
        console.error('Error fetching folder contents:', error);
      }
    });
  }
  onSearch(event: any): void {
    const searchValue = event.target.value.trim();
    if (searchValue) {
      this.foldersService.searchFolders(searchValue).subscribe(response => {
        this.folders = response.results;
        this.appendToTable(this.folders, this.documents, null);
      });
    } else {
      this.clearTable();
    }
  }

  clearTable(): void {
    const tbody = document.querySelector('.folder-right-conten table tbody') as HTMLElement;
    if (tbody) {
      tbody.innerHTML = '';
    }
  }
 
  
  onCutClickf(event: Event) {
    this.cutElementf.nativeElement.style.display = 'none';
    this.pasteElementf.nativeElement.style.display = 'block';
  
    if (this.cutElementf) {
      const addValue = this.cutElementf.nativeElement.getAttribute('chua');
      if (addValue !== null && addValue !== '') {
        this.cutItemIdf = parseInt(addValue, 10);
        console.log('Cut element attribute (chua):', addValue);
        console.log('Cut item ID:', this.cutItemIdf);
      } else {
        console.warn('Cut element does not have a valid attribute "chua"');
        this.cutItemIdf = null;
      }
    } else {
      console.warn('cutElementf is not defined');
    }
  }
  
  onPasteClickf(event: Event) {
    this.pasteElementf.nativeElement.style.display = 'none';
    this.cutElementf.nativeElement.style.display = 'block';
  
    if (this.cutItemIdf !== null) {

      if (this.rightClickedOnFolderDropArea) {
        const idKhaiValue = this.folderDropAreaRef.nativeElement.getAttribute('id-khai');
        const newParentFileId = idKhaiValue ? parseInt(idKhaiValue, 10) : null;
  
        if (newParentFileId !== null) {
          const updateData = { folder: newParentFileId };
  
          console.log('Gửi dữ liệu cập nhật:', updateData);
  
          this.foldersService.updateFile(this.cutItemIdf, updateData).subscribe(
            updatedFile => {
              console.log('Đã cập nhật file:', updatedFile);

            },
            error => {
              console.error('Lỗi khi cập nhật folder:', error);
            }
          );
        } else {
          console.warn('Dữ liệu không hợp lệ để thực hiện cập nhật');
        }
      } else {

        const addValue = this.pasteElementf.nativeElement.getAttribute('add');
        if (addValue !== null && addValue !== '') {
          const newParentFileId = parseInt(addValue, 10);
  
          const updateData = { folder: newParentFileId };
  
          console.log('Gửi dữ liệu cập nhật:', updateData);
  
          this.foldersService.updateFile(this.cutItemIdf, updateData).subscribe(
            updatedFile => {
              console.log('Đã cập nhật file:', updatedFile);

            },
            error => {
              console.error('Lỗi khi cập nhật folder:', error);
            }
          );
        } else {
          console.warn('Dữ liệu không hợp lệ để thực hiện cập nhật');
        }
      }
    } else {
      console.warn('Không có tài liệu để cập nhật');
    }
  

    this.rightClickedOnFolderDropArea = false;
  }
  deleteFile(event: Event): void {
    const target = event.target as HTMLElement;
    const idAttr = target.closest('li')?.getAttribute('chua');
    if (idAttr) {
      const id = parseInt(idAttr, 10);
      if (!isNaN(id)) {
        this.foldersService.deleteFileById(id).subscribe({
          next: () => {
            console.log(`File with ID ${id} has been deleted.`);

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


onCutClick() {
  this.cutElement.nativeElement.style.display = 'none';
  this.pasteElement.nativeElement.style.display = 'block';

  if (this.cutElement) {
    const addValue = this.cutElement.nativeElement.getAttribute('add');
    this.cutItemId = parseInt(addValue, 10);
  }
}
@HostListener('contextmenu', ['$event'])
onRightClick(event: MouseEvent) {
  if (event.target === this.folderDropAreaRef.nativeElement) {
    this.rightClickedOnFolderDropArea = true;
  }
}

onPasteClick(event: MouseEvent) {
  this.pasteElement.nativeElement.style.display = 'none';
  this.cutElement.nativeElement.style.display = 'block';


  const rightClickedOnFolderDropArea = event && (event.button === 2 || event.which === 3);
  if (rightClickedOnFolderDropArea) {
    const idKhaiValue = this.folderDropAreaRef.nativeElement.getAttribute('id-khai');
    const newParentFolderId = idKhaiValue ? parseInt(idKhaiValue, 10) : null;

    if (newParentFolderId !== null && this.cutItemId !== null) {
      const folderToUpdate = this.results.find(result => result.id === this.cutItemId);
      if (folderToUpdate) {

        this.foldersService.updateFolder(folderToUpdate.id, { parent_folder: newParentFolderId }).subscribe(
          updatedFolder => {
            folderToUpdate.parent_folder = newParentFolderId;
            this.cutItemId = null; 
          },
          error => {
            console.error('Failed to update folder:', error); 
          }
        );
      }
    }
  } else {

    const addValue = this.pasteElement.nativeElement.getAttribute('add');
    const newParentFolderId = parseInt(addValue, 10);

    if (this.pasteElement && this.cutItemId !== null) {
      const folderToUpdate = this.results.find(result => result.id === this.cutItemId);
      if (folderToUpdate) {

        this.foldersService.updateFolder(folderToUpdate.id, { parent_folder: newParentFolderId }).subscribe(
          updatedFolder => {
            folderToUpdate.parent_folder = newParentFolderId; 
            this.cutItemId = null; 
          },
          error => {
            console.error('Failed to update folder:', error); 
          }
        );
      }
    }
  }
}



  toggleElementVisibility(elementRef: ElementRef) {
    const element = elementRef.nativeElement as HTMLElement;
    element.style.display = element.style.display === 'none' ? '' : 'none';
  }
  getDocumentsByFolderId(folderId: number) {
    this.foldersService.getresults(folderId).subscribe({
      next: (data: SRC) => {
        this.documents = data.documents.filter(document => document.folder !== null);
        this.filteredDocuments = this.documents.filter(doc => doc.folder === folderId);
        this.initializeFolders();
      },
      error: error => {
        console.error('Error fetching results:', error);
      }
    });
  }
  deleteMultipleItems(event: MouseEvent) {
    const target = event.currentTarget as HTMLElement;
    const add2Attribute = target.getAttribute('add2');
    if (add2Attribute) {
      const idsToDelete = add2Attribute.split(',').map(id => parseInt(id.trim(), 10));

      this.foldersService.bulkDeleteFolders(idsToDelete).subscribe(
        () => {

          this.results = this.results.filter(result => !idsToDelete.includes(result.id));
          console.log(`IDs ${idsToDelete.join(', ')} have been deleted.`);
          this.loadFolders();
        },
        error => {
          console.error('Error deleting multiple items:', error);
        }
      );
    }
  }
  deleteItem(event: MouseEvent) {
    const target = event.currentTarget as HTMLElement;
    const addAttribute = target.getAttribute('add');
    if (addAttribute) {
      const idToDelete = parseInt(addAttribute, 10);

      this.foldersService.deleteFolder(idToDelete).subscribe(
        () => {

          this.results = this.results.filter(result => result.id !== idToDelete);
          console.log(`ID ${idToDelete} has been deleted.`);
          this.loadFolders();
          this.loadFolderContents;
        },
        error => {
          console.error('Error deleting item:', error);
        }
      );
    }
  }
  showRenameFolder(event: Event): void {
    const liElement = (event.currentTarget as HTMLElement).closest('li');
    if (liElement) {
      const folderId = liElement.getAttribute('add');
      if (folderId) {
        this.renameFolderId = parseInt(folderId);
        const result = this.results.find(item => item.id === this.renameFolderId);
        if (result) {
          this.renameFolderName = result.name;
          const inputContainer = document.getElementById('sub-reanmefolder-container');
          if (inputContainer) {
            inputContainer.style.display = 'block';
          }
        }
      }
    }
  }

  onRenameFolder(event: Event): void {
    event.preventDefault();
    if (this.renameFolderId !== null) {
      const oldFolder = this.results.find(item => item.id === this.renameFolderId);
      if (oldFolder) {
        const updateData = {
          name: this.renameFolderName,
          parent_folder: oldFolder.parent_folder !== null ? oldFolder.parent_folder : undefined
        };
  
        this.foldersService.updateFolder(this.renameFolderId, updateData)
          .subscribe(updatedFolder => {
            const index = this.results.findIndex(item => item.id === this.renameFolderId);
            if (index !== -1) {
              this.results[index].name = updatedFolder.name;
              this.results[index].parent_folder = updatedFolder.parent_folder;
              this.loadFolders();
            }
          }, error => {
            console.error('Error updating folder:', error);

          });
      }
    }
  }
  
  
  
  
  loadFolders(): void {

    this.foldersService.getResults().subscribe(
      (response: any) => {
        this.results = response.results; 
      },
      error => {
        console.error('Failed to load results:', error);
      }
    );
  
    this.foldersService.getFoldersAndDocuments().subscribe(
      (response: any) => {
        this.folders = response.folders; 
        this.documents = response.documents; 
      },
      error => {
        console.error('Failed to load folders and documents:', error);
      }
    );
  
    this.foldersService.getdocument().subscribe(
      (data: { thesis: Document[]; }) => {
        this.documents = data.thesis; 
      },
      error => {
        console.error('Failed to load documents:', error);
      }
    );
    
    
  }
  
  

  showInput(event: Event): void {
    const liElement = (event.currentTarget as HTMLElement).closest('li');
    if (liElement) {
      this.parent_folder = liElement.getAttribute('add') ? parseInt(liElement.getAttribute('add')) : null;
      const inputContainer = document.getElementById('sub-folder-container');
      if (inputContainer) {
        inputContainer.style.display = 'block';
      }
    }
  }
  
  
  showRenameFile(event: Event): void {
    const inputContainer1 = document.getElementById('sub-reanamefile-container');
    if (inputContainer1) {
      inputContainer1.style.display = 'block';
      const inputElement = inputContainer1.querySelector('input[name="Renamefile"]') as HTMLInputElement;
      if (inputElement) {
        inputElement.focus();
      }
    }
    const liElement = (event.currentTarget as HTMLElement).closest('li');
    if (liElement) {
      const documentId = liElement.getAttribute('chua');
      if (documentId) {
        this.renameFileId = parseInt(documentId, 10);
        const result = this.documents.find(item => item.id === this.renameFileId);
        if (result) {
          this.renameFileName = result.title;
        }
      }
    }
  }

  onRenameFile(event: Event): void {
    event.preventDefault();
    const inputContainer = document.getElementById('sub-reanamefile-container');
    if (inputContainer) {
      inputContainer.style.display = 'none';
    }
    if (this.renameFileId !== null) {
      const oldDocument = this.documents.find(item => item.id === this.renameFileId);
      if (oldDocument) {
        const updateData: Partial<Document> = {
          title: this.renameFileName,
          folder: oldDocument.folder !== null ? oldDocument.folder : undefined
        };

        this.foldersService.updateFile(this.renameFileId, updateData)
          .subscribe(
            updatedFile => {
              const index = this.documents.findIndex(item => item.id === this.renameFileId);
              if (index !== -1) {
                this.documents[index].title = updatedFile.title;
                this.documents[index].folder = updatedFile.folder;
                this.loadFolders();
              }
            },
            error => {
              console.error('Error updating file:', error);

            }
          );
      }
    }
  }


  onAddFolder(): void {
    if (this.folderName.trim()) {
      const folderData = {
        name: this.folderName,
        parent_folder: this.parent_folder ? this.parent_folder : null
      };
  
      this.foldersService.createFolder(folderData).subscribe(response => {
        this.folders.push(response);
        this.cdr.detectChanges(); 
  
        this.folderName = '';
        const inputContainer = document.getElementById('sub-folder-container');
        if (inputContainer) {
          inputContainer.style.display = 'none';
        }
  
        this.loadFolderContents(this.parent_folder ? this.parent_folder : response.id);
      });
    }
  }
  
  
  addGridStyles(): void {
    if (this.addedStyleElement) {
      return;
    }

    const style = this.renderer.createElement('style');
    style.textContent = `
      .folder-contents.grid-layout tbody {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
          grid-gap: 0.2px;
      }
      .folder-contents.grid-layout tr th:nth-child(2),
      .folder-contents.grid-layout tr th:nth-child(3),
      .folder-contents.grid-layout tr th:nth-child(4) {
          display: none;
      }
      tbody .folder th {
          padding: 0;
          margin-left: 0;
      }
      tbody .folder th .fa-solid {
          color: gold;
      }
      tbody .folder {
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          margin: 0;
          border-style: none;
          padding-left: 0;
      }
      .table-striped > tbody > tr:nth-of-type(odd) > * {
          --bs-table-color-type: var(--bs-table-striped-color);
          --bs-table-bg-type: none !important;
      }
      thead, tbody, tfoot, tr, td, th {
          border-color: none !important;
          border-style: none !important;
          border-width: none !important;
          box-shadow: none;
          border: none;
      }
      tbody .folder tr {
          background: none;
          --bs-table-bg-type: none;
      }
      tbody .folder th:hover {
          border: 1px solid blue;
          padding: 10px;
      }
      tbody .folder:hover {
          background: rgba(245, 245, 245, 0);
      }
      tbody .document:hover {
          background: #ffffff00;
          border: 1px solid blue;
      }
      tbody .document {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
      }
      table {
          box-shadow: none !important;
      }
      .folder-contents .border {
          border:none !important;
      }
      .folder-contents .shadow-sm {
          box-shadow: none !important; 
      }
      .border {
          border: none !important;
      }
      .folder-contents tbody .document th {
          margin-top: 10px;
      }
      .folder-contents table {
          border: none;
      }
      table th,
      table td {
          border: none;
      }
      .folder-contents.grid-layout thead {
          display: none;
      }
      .folder-contents .folder:hover {
          border: 1px solid blue;
      }
      .folder-contents.grid-layout tr {
          width: 100px; 
          height: 150px; 
          display: block; 
          display: flex;
          flex-direction: column;
          margin-left: 30px;
          border: none;
      }
      .folder-contents.grid-layout tr p {
          color: black;
      }
      .folder-contents.grid-layout tr .fa-solid {
          font-size: 80px;
          display: block; 
      }
    `;

    this.renderer.appendChild(document.head, style);
    this.addedStyleElement = style;

    const folderContents = document.querySelector('.folder-contents');
    if (folderContents) {
      this.renderer.addClass(folderContents, 'grid-layout');
    }
  }

  removeGridStyles(): void {
    if (this.addedStyleElement) {
      this.renderer.removeChild(document.head, this.addedStyleElement);
      this.addedStyleElement = null;
    }

    const folderContents = document.querySelector('.folder-contents');
    if (folderContents) {
      this.renderer.removeClass(folderContents, 'grid-layout');
    }
  }
  addEventListenerss(): void {
    const folderLeft = this.elementRef.nativeElement.querySelector('#folderLeft') as HTMLElement;
    const folderright = this.elementRef.nativeElement.querySelector('#folderrightt');
    const folderContainer = this.elementRef.nativeElement.querySelector('.folder-container');
    const zoom = this.elementRef.nativeElement.querySelector('#zoomImg');
    const contextMenu = this.elementRef.nativeElement.querySelector('#contextMenu');
    const toggleButton = this.elementRef.nativeElement.querySelector('#toggleButton');
    const subFolderContainer = this.elementRef.nativeElement.querySelector('#sub-folder-container');
    const subRenameFileContainer = this.elementRef.nativeElement.querySelector('#sub-reanamefile-container');
    const subRenameFolderContainer = this.elementRef.nativeElement.querySelector('#sub-reanmefolder-container');
  
   
    const amButtons = this.elementRef.nativeElement.querySelectorAll('.am');
  
    amButtons.forEach(amButton => {
      amButton.addEventListener('click', (event) => {
        const target = event.target as HTMLElement;
        const action = target.textContent?.trim();
  
       
        subFolderContainer.style.display = 'none';
        subRenameFileContainer.style.display = 'none';
        subRenameFolderContainer.style.display = 'none';
  
        switch (action) {
          case 'New folder...':
            subFolderContainer.style.display = 'block';
            break;
          case 'Rename File...':
            subRenameFileContainer.style.display = 'block';
            break;
          case 'Rename Folder...':
            subRenameFolderContainer.style.display = 'block';
            break;
          default:
            break;
        }
  
        contextMenu.style.display = 'none';
      });
    });
    document.addEventListener('mousedown', event => {
      const targetElement = event.target as HTMLElement;
  

      if (!subFolderContainer.contains(targetElement)
          && !subRenameFileContainer.contains(targetElement)
          && !subRenameFolderContainer.contains(targetElement)
          && !contextMenu.contains(targetElement)) {
        subFolderContainer.style.display = 'none';
        subRenameFileContainer.style.display = 'none';
        subRenameFolderContainer.style.display = 'none';
        contextMenu.style.display = 'none';
      }
    });
  
  
    document.getElementById('sss').addEventListener('click', function() {
      const contextMenu1 = document.querySelector('.sub-folder-container') as HTMLElement;
      if (contextMenu1) {
          contextMenu1.style.display = 'none';
      }
    });
  
    folderLeft.addEventListener('click', () => {
      this.hideContextMenu();
    });
  
    folderright.addEventListener('click', () => {
      this.hideContextMenu();
    });
  
    
    folderLeft.addEventListener('contextmenu', event => {
      event.preventDefault(); 
      this.showContextMenu(event.clientX, event.clientY); 
    });
  
    folderright.addEventListener('contextmenu', event => {
      event.preventDefault(); 
      this.showContextMenu(event.clientX, event.clientY); 
    });
  
    document.addEventListener('mousedown', event => {
      const targetElement = event.target as HTMLElement;
  
      const clickedInsideContextMenu = contextMenu.contains(targetElement);
      const clickedInsideFolderContainer = folderContainer.contains(targetElement);
      const clickedInsideAddFolder = targetElement.classList.contains('addfolder') || targetElement.closest('.addfolder');
      const clickedInsideAm = targetElement.classList.contains('am') || targetElement.closest('.am'); 
  
      if (!clickedInsideContextMenu && !clickedInsideAddFolder && !clickedInsideAm) {
        this.hideContextMenu();
      }
  
      if (clickedInsideAm) {
        event.preventDefault();
      }
    });
  
    toggleButton.addEventListener('click', () => {
      this.toggleEvents();
    });
  }
  

  showContextMenu(x: number, y: number): void {
    const contextMenu = this.elementRef.nativeElement.querySelector('#contextMenu');
    if (contextMenu) {
      contextMenu.style.display = 'block';
      contextMenu.style.left = x + 'px';
      contextMenu.style.top = y + 'px';
    }
  }
  toggleEvents() {
    
  }
  hideContextMenu(): void {
    const contextMenu = this.elementRef.nativeElement.querySelector('#contextMenu');
    if (contextMenu) {
      contextMenu.style.display = 'none';
    }
  }
  initializeFolders(): void {
    const foldersContainer = this.elementRef.nativeElement.querySelector('#folders-container');
    if (foldersContainer) {

      const allFolders = [...this.folders, ...this.results];
      foldersContainer.innerHTML = '';
  

      const folderMap = new Map<number, Folders[]>();
  

      allFolders.forEach(folder => {
        const parentId = folder.parent_folder ?? null;
        if (!folderMap.has(parentId)) {
          folderMap.set(parentId, []);
        }
        folderMap.get(parentId)?.push(folder);
      });
  

      const documentMap = new Map<number, Document[]>();
  

      this.thesis.forEach(document => {
        if (document.folder !== null && document.folder !== undefined) {
          const folderId = document.folder;
          if (!documentMap.has(folderId)) {
            documentMap.set(folderId, []);
          }
          documentMap.get(folderId)?.push(document);
        }
      });
  

      const createFolders = (parentId: number | null, parentDiv: HTMLElement | null): void => {
        const children = folderMap.get(parentId) || [];
        children.forEach(folder => {
          const folderHTML = this.createFolderHTML(folder);
          if (parentDiv) {
            this.renderer.appendChild(parentDiv, folderHTML);
          } else {
            this.renderer.appendChild(foldersContainer, folderHTML);
          }
  

          const documents = documentMap.get(folder.id) || [];
          const childrenContainer = folderHTML.querySelector('.children-container') as HTMLElement;
          documents.forEach(document => {
            const documentHTML = this.createDocumentHTML(document);
            this.renderer.appendChild(childrenContainer, documentHTML);
          });
  

          createFolders(folder.id, folderHTML.querySelector('.children-container') as HTMLElement);
        });
      };
  

      createFolders(null, null);
    }
  }

  initializeDocuments(): void {
    const documentsContainer = this.elementRef.nativeElement.querySelector('#documents-container');
    documentsContainer.setAttribute('pxngxPreventRightClick', '');
    if (documentsContainer) {
      documentsContainer.innerHTML = '';
      const addedDocumentFilenames = new Set<string>();
  
      this.documents.forEach(doc => {
        const folder = this.findFolderById(doc.folder);
        if (!addedDocumentFilenames.has(doc.filename)) {
          if (folder && folder.id > 0) {
            const folderDiv = this.findFolderDiv(folder.id);
            if (folderDiv) {
              const documentsContainerInFolder = folderDiv.querySelector('.documents-container') as HTMLElement;
              if (documentsContainerInFolder && !documentsContainerInFolder.querySelector(`.document[data-document-id="${doc.id}"]`)) {
                const documentHTML = this.createDocumentHTML(doc);
                this.renderer.appendChild(documentsContainerInFolder, documentHTML);
                addedDocumentFilenames.add(doc.filename);
              }
            }
          } else {
            if (!documentsContainer.querySelector(`.document[data-document-id="${doc.id}"]`)) {
              const documentHTML = this.createDocumentHTML(doc);
              this.renderer.appendChild(documentsContainer, documentHTML);
              addedDocumentFilenames.add(doc.filename);
            }
          }
        }
      });
    }
  }
  

  addEventListeners(): void {

    const folderChaElements = this.elementRef.nativeElement.querySelectorAll('.folder-cha');
    folderChaElements.forEach(item => {
      this.renderer.listen(item, 'dblclick', (event: Event) => {
        const target = event.currentTarget as HTMLElement;
        const folderElement = target.closest('.folder') as HTMLElement;
        const folderId = Number(folderElement?.dataset.folderId);
        this.confirmDisplayFolderContents(folderId);
      });
    });
  

    const folderRows = this.elementRef.nativeElement.querySelectorAll('tr[data-folder-id]');
    folderRows.forEach(row => {
 
      row.removeEventListener('click', this.handleRowClick);
      
 
      this.renderer.listen(row, 'dblclick', (event: Event) => {
        const target = event.currentTarget as HTMLTableRowElement;
        const folderId = Number(target.dataset.folderId);
        this.confirmDisplayFolderContents(folderId);
      });
    });
  
   
    const folderLeft = this.elementRef.nativeElement.querySelector('#folderLeft');
    if (folderLeft) {
      const resizeHandle = folderLeft.querySelector('.resize-handle') as HTMLElement;
      if (resizeHandle) {
        let startX: number;
        let startWidth: number;
  
        const resizeWidth = (event: MouseEvent) => {
          const newWidth = startWidth + (event.clientX - startX);
          folderLeft.style.width = `${newWidth}px`; 
        
          const folderRight = this.elementRef.nativeElement.querySelector('.folder-right') as HTMLElement;
          if (folderRight) {
            folderRight.style.width = `calc(100% - ${newWidth}px)`;
          }
        };
        
  
        const stopResize = () => {
          document.removeEventListener('mousemove', resizeWidth);
          document.removeEventListener('mouseup', stopResize);
        };
  
        this.renderer.listen(resizeHandle, 'mousedown', (event: MouseEvent) => {
          startX = event.clientX;
          startWidth = parseInt(window.getComputedStyle(folderLeft).width, 10);
          document.addEventListener('mousemove', resizeWidth);
          document.addEventListener('mouseup', stopResize);
        });
      }
    }
  }
  
  handleRowClick(event: Event) {
    const target = event.currentTarget as HTMLTableRowElement;
    const folderId = Number(target.dataset.folderId);
  
  }
  handleFolderRightTimClick(): void {
    const folderRightTim = this.elementRef.nativeElement.querySelector('.folder-right-tim');
    if (!folderRightTim) {
      console.error('Element .folder-right-tim not found');
      return;
    }
  
    folderRightTim.addEventListener('click', (event) => {
      if (folderRightTim.querySelector('input')) {
        event.stopPropagation();
        return;
      }
  
      const originalContent = folderRightTim.innerHTML;
      const divs = folderRightTim.querySelectorAll('div');
      const formattedContent = Array.from(divs).map(div => (div as HTMLElement).textContent?.trim() || '').join('/');
  
      // Tạo input element
      const inputElement = document.createElement('input');
      inputElement.type = 'text';
      inputElement.placeholder = 'Nhập đường dẫn...';
      inputElement.value = formattedContent;
  

      const handleEnterKey = (event: KeyboardEvent) => {
        if (event.key === 'Enter') {
          const newPath = inputElement.value.trim();
  
          if (!newPath.startsWith('/')) {
            console.error('Đường dẫn phải bắt đầu bằng dấu gạch chéo "/"');
            return;
          }
  
          folderRightTim.innerHTML = newPath;
          this.displayFolderPath(newPath);
  
          const pathSegments = newPath.split('/').filter(segment => segment !== '');
          const folderName = pathSegments[pathSegments.length - 1];
  
          this.foldersService.getResults().subscribe({
            next: (response: { results: Results[] }) => {
              const folder = response.results.find(f => f.name === folderName);
              if (folder) {
                console.log(`path của folder '${folderName}': ${folder.path}`);
                this.verifyAndLogPath(folder.path, pathSegments, response.results);
              } else {
                console.error(`Folder '${folderName}' không được tìm thấy.`);
              }
            },
            error: (error: HttpErrorResponse) => {
              console.error('Error fetching results:', error);
            }
          });
  
  
          folderRightTim.innerHTML = originalContent;
          document.removeEventListener('click', handleClickOutside);
        }
      };
  
  
      const handleClickOutside = (event: MouseEvent) => {
        if (!folderRightTim.contains(event.target as Node)) {
          folderRightTim.innerHTML = originalContent;
          document.removeEventListener('click', handleClickOutside);
        }
      };
  

      inputElement.addEventListener('keyup', handleEnterKey);
  

      folderRightTim.innerHTML = '';
      folderRightTim.appendChild(inputElement);
      inputElement.focus();
      document.addEventListener('click', handleClickOutside);
    });
  }
  
  private verifyAndLogPath(folderPath: string, pathSegments: string[], results: Results[]): void {
    const pathIds = folderPath.split('/').map(id => parseInt(id, 10));
    let isPathValid = true;
    let folder;
  
    for (let i = 0; i < pathIds.length; i++) {
      folder = results.find(f => f.id === pathIds[i]);
      if (!folder || folder.name !== pathSegments[i]) {
        isPathValid = false;
        break;
      }
    }
  
    if (isPathValid && folder) {
      this.loadFolderContentss(folder.id);
      this.displayFolderPath(folder.path);
    } else {
      console.error('Đường dẫn không hợp lệ.');
    }
  }
  
  ngAfterViewInit(): void {
    this.handleFolderRightTimClick();
  }  


handleFolderClick(folderId: number): void {
  this.foldersService.getFolders(folderId).subscribe({
    next: (response: { folders: Folders[] }) => {
      const folder = response.folders.find(f => f.id === folderId);
      if (folder) {
        this.displayFolderPath(folder.path);
      } else {
        console.error(`Folder with ID ${folderId} not found.`);
      }
    },
    error: (error: HttpErrorResponse) => {
      console.error('Error fetching folders:', error);
    }
  });
}
findFolderByIds(folderId: number, results: Results[]): Results | undefined {
  return results.find(folder => folder.id === folderId);
}
displayFolderPath(path: string): void {
  const folderRightTim = this.elementRef.nativeElement.querySelector('.folder-right-tim');
  if (folderRightTim) {

    folderRightTim.innerHTML = '';

    const pathSegments = path.split('/');

 
    const logoFolderDiv = document.createElement('div');
    logoFolderDiv.classList.add('logo-folder');
    logoFolderDiv.innerHTML = `
      <i class="fa-solid fa-folder"></i> <i class="fa-solid fa-chevron-right"></i>
    `;
    folderRightTim.appendChild(logoFolderDiv);

    this.foldersService.getResults().subscribe({
      next: (response: { results: Results[] }) => {
        pathSegments.forEach((segment, index) => {
          const folderId = parseInt(segment, 10);
          const folder = response.results.find(f => f.id === folderId);


          if (folder) {
            const folderName = folder.name;

            const folderDiv = document.createElement('div');
            folderDiv.classList.add('ten-folder');
            folderDiv.dataset.folderId = folderId.toString();
            folderDiv.innerHTML = `
              <p>${folderName}</p>
              ${index < pathSegments.length - 1 ? '<i class="fa-solid fa-chevron-right"></i>' : ''}
            `;
            folderRightTim.appendChild(folderDiv);


            this.renderer.listen(folderDiv, 'click', () => {
              this.loadFolderContentss(folder.id); 
              this.displayFolderPath(folder.path);
            });
          } else {
            console.error(`Folder not found for ID: ${folderId}`);
          }
        });
      },
      error: (error: HttpErrorResponse) => {
        console.error('Error fetching results:', error);
      }
    });
  } else {
    console.error('Element .folder-right-tim not found');
  }
}




  confirmDisplayFolderContents(folderId: number): void {
    this.displayFolderContents(folderId);
  }

  displayFolderContents(folderId: number, parentRow: HTMLTableRowElement | null = null): void {
    const tableBody = this.elementRef.nativeElement.querySelector('.folder-contents tbody');
    if (tableBody) {
      const rowsToRemove = parentRow
      ? tableBody.querySelectorAll(`.child-of-folder-${folderId}`)
      : tableBody.querySelectorAll('tr');
      rowsToRemove.forEach(row => row.remove());

      const childFolders = this.folders.filter(folder => folder.parent_folder === folderId);
      const childResults = this.results.filter(result => result.parent_folder === folderId);
      const allChildFolders = [...childFolders, ...childResults];

      allChildFolders.forEach(folder => {
        const row = this.createFolderRowHTML(folder, folderId);
        if (parentRow) {
          parentRow.insertAdjacentElement('afterend', row);
        } else {
          tableBody.appendChild(row);
        }
      });

      const childDocuments = this.documents.filter(doc => doc.folder === folderId);
      childDocuments.forEach(doc => {
        const row = this.createDocumentRowHTML(doc, folderId);
        if (parentRow) {
          parentRow.insertAdjacentElement('afterend', row);
        } else {
          tableBody.appendChild(row);
        }
      });

      this.addRowEventListeners();
    }
  }

  createFolderRowHTML(folder: Folders, parentId: number): HTMLElement {
    const row = document.createElement('tr');
    row.classList.add(`child-of-folder-${parentId}`);
    row.dataset.folderId = folder.id.toString();
    this.renderer.setAttribute(row, 'pxngxPreventRightClick', '');

    const nameCell = document.createElement('td');
    row.setAttribute('pxngxPreventRightClick', '');
    const folderIcon = document.createElement('i');
    folderIcon.classList.add('fa-solid', 'fa-folder');
    const folderName = document.createElement('p');
    folderName.textContent = folder.name;
    nameCell.appendChild(folderIcon);
    nameCell.appendChild(folderName);

    const dateCell = document.createElement('td');
    dateCell.textContent = '11/10/2002'; 

    const typeCell = document.createElement('td');
    typeCell.textContent = 'File Folder';

    const sizeCell = document.createElement('td');
    sizeCell.textContent = '2 KB';

    row.appendChild(nameCell);
    row.appendChild(dateCell);
    row.appendChild(typeCell);
    row.appendChild(sizeCell);

    return row;
  }

  createDocumentRowHTML(doc: Document, parentId: number): HTMLElement {
    const row = document.createElement('tr');
    row.classList.add(`child-of-folder-${parentId}`);
    row.dataset.documentId = doc.id.toString();
    this.renderer.setAttribute(row, 'pxngxPreventRightClick', '');

    const nameCell = document.createElement('td');
    row.setAttribute('pxngxPreventRightClick', '');
    const fileIcon = document.createElement('i');
    fileIcon.classList.add('fa-solid', 'fa-file');
    const fileName = document.createElement('p');
    fileName.textContent = doc.filename;
    nameCell.appendChild(fileIcon);
    nameCell.appendChild(fileName);

    const dateCell = document.createElement('td');
    dateCell.textContent = '11/10/2002'; 

    const typeCell = document.createElement('td');
    typeCell.textContent = 'txt'; 

    const sizeCell = document.createElement('td');
    sizeCell.textContent = '2 KB'; 

    row.appendChild(nameCell);
    row.appendChild(dateCell);
    row.appendChild(typeCell);
    row.appendChild(sizeCell);

    return row;
  }
  appendFoldersAndDocuments(folders: Folders[], documents: Document[], container: HTMLElement): void {
    folders.forEach(folder => {
      const folderHTML = this.createFolderHTML(folder);
      this.renderer.appendChild(container, folderHTML);
    });
    documents.forEach(document => {
      const documentHTML = this.createDocumentHTML(document);
      this.renderer.appendChild(container, documentHTML);
    });
  }
  createFolderHTML(folder: Folders): HTMLElement {
    const folderDiv = document.createElement('div');
    folderDiv.classList.add('folder');
    folderDiv.dataset.folderId = folder.id.toString();
    folderDiv.dataset.folderPath = folder.path;
    this.renderer.setAttribute(folderDiv, 'pxngxPreventRightClick', '');
  
    const folderIcon = document.createElement('i');
    folderIcon.classList.add('fa', 'fa-solid', 'fa-chevron-right');
  
    const folderIconFolder = document.createElement('i');
    folderIconFolder.classList.add('fa', 'fa-solid', 'fa-folder');
  
    const folderName = document.createElement('p');
    folderName.textContent = folder.name;
  
    const folderHeader = document.createElement('div');
    folderHeader.classList.add('folder-cha');
    folderHeader.setAttribute('pxngxPreventRightClick', '');
    folderHeader.appendChild(folderIcon);
    folderHeader.appendChild(folderIconFolder);
    folderHeader.appendChild(folderName);
  
    folderDiv.appendChild(folderHeader);
  
    const childrenContainer = document.createElement('div');
    childrenContainer.classList.add('children-container');
    childrenContainer.setAttribute('pxngxPreventRightClick', '');
    childrenContainer.style.display = 'none';
    folderDiv.appendChild(childrenContainer);
  
    this.renderer.listen(folderHeader, 'click', (event: Event) => {
      event.stopPropagation();
  
      const clickedFolderId = parseInt(folderDiv.dataset.folderId || '0', 10);
      const clickedFolderPath = folderDiv.dataset.folderPath || '';
  
      if (!(event as MouseEvent).ctrlKey) {
        const selectedItems = document.querySelectorAll('.selected');
        selectedItems.forEach(item => item.classList.remove('selected'));
      }
  
      folderDiv.classList.toggle('selected');
  
      this.foldersService.fetchfolderandDocuments(clickedFolderId).subscribe({
        next: (data) => {
          this.appendToTable(data.folders, data.documents, clickedFolderId);
          this.displayFolderPath(clickedFolderPath);
  
          const folderDropArea = document.getElementById('folderDropArea');
          if (folderDropArea) {
            this.renderer.setAttribute(folderDropArea, 'id-khai', clickedFolderId.toString());
          }
        },
        error: (error) => {
          console.error('Error fetching folder and documents:', error);
        }
      });
    });
  
    this.renderer.listen(folderIcon, 'click', (event: Event) => {
      event.stopPropagation();
  
      if (childrenContainer.style.display === 'none') {
        childrenContainer.style.display = 'block';
        folderIcon.style.transform = 'rotate(90deg)';
        folderIconFolder.classList.replace('fa-folder', 'fa-folder-open');
  
        childrenContainer.innerHTML = '';
  
        const clickedFolderId = parseInt(folderDiv.dataset.folderId || '0', 10);
        this.foldersService.fetchfolderandDocuments(clickedFolderId).subscribe({
          next: (data) => {
            this.appendFoldersAndDocuments(data.folders, data.documents, childrenContainer);
          },
          error: (error) => {
            console.error('Error fetching folder and documents:', error);
          }
        });
      } else {
        childrenContainer.style.display = 'none';
        folderIcon.style.transform = '';
        folderIconFolder.classList.replace('fa-folder-open', 'fa-folder');
      }
    });
  
    return folderDiv;
  }
  
  createDocumentHTML(doc: Document): HTMLElement {
    const documentDiv = document.createElement('div');
    documentDiv.classList.add('document');
    documentDiv.setAttribute('pxngxPreventRightClick', '');
    documentDiv.dataset.documentId = doc.id.toString();
  
    const documentIcon = document.createElement('i');
    documentIcon.classList.add('fa', 'fa-file');
  
    const documentName = document.createElement('p');
    documentName.textContent = doc.filename;
  
    const documentContainer = document.createElement('div');
    documentContainer.classList.add('document-container');
    documentContainer.appendChild(documentIcon);
    documentContainer.appendChild(documentName);
  
    documentDiv.appendChild(documentContainer);
  
    this.renderer.listen(documentDiv, 'click', (event: MouseEvent) => {
      if (!event.ctrlKey) {
        const selectedItems = document.querySelectorAll('.selected');
        selectedItems.forEach(item => item.classList.remove('selected'));
      }
      documentDiv.classList.toggle('selected');
    });
  
    return documentDiv;
  }


  findFolderById(folderId: number): Folders | undefined {
    return this.folders.find(folder => folder.id === folderId);
  }
  getFolderNameById(id: number): string | null {
    const folder = this.results.find(f => f.id === id);
    return folder ? folder.name : null;
}

  findFolderDiv(folderId: number): HTMLElement | null {
    const foldersContainer = document.getElementById('folders-container');
    return foldersContainer?.querySelector(`.folder[data-folder-id="${folderId}"]`) as HTMLElement | null;
  }

  addRowEventListeners(): void {
    const folderRows = this.elementRef.nativeElement.querySelectorAll('tr[data-folder-id]');
    folderRows.forEach(row => {
      row.addEventListener('click', (event) => {
        if (!event.ctrlKey) {

          const selectedItems = document.querySelectorAll('.selected');
          selectedItems.forEach(item => item.classList.remove('selected'));
        }

        row.classList.toggle('selected');
      });
    
      this.renderer.listen(row, 'dblclick', (event: Event) => {
        const target = event.currentTarget as HTMLTableRowElement;
        const folderId = Number(target.dataset.folderId);
  
    
        const result = this.results.find(result => result.id === folderId);
        if (result) {
          const folderPath = result.path;
  
       
          const folderRightTim = document.querySelector('.folder-right-tim');
          if (folderRightTim) {
            folderRightTim.innerHTML = ''; 
  
         
            const logoFolderDiv = document.createElement('div');
            logoFolderDiv.classList.add('logo-folder');
  
            const folderIcon = document.createElement('i');
            folderIcon.classList.add('fa', 'fa-solid', 'fa-folder');
  
            const chevronIcon = document.createElement('i');
            chevronIcon.classList.add('fa', 'fa-regular', 'fa-folder-open');
  
         
            logoFolderDiv.appendChild(folderIcon);
            logoFolderDiv.appendChild(chevronIcon);
  
       
            folderRightTim.appendChild(logoFolderDiv);
  
          
            this.loggedFolderPath = folderPath;
  
           
            this.confirmDisplayFolderContents(folderId);
  
 
            const numberArray = folderPath.split('/').map(Number);
  

            numberArray.forEach(number => {

              const folderId = parseInt(number.toString(), 10);
              const folderName = this.getFolderNameById(folderId);
  
              if (folderName) {

                const tenFolderDiv = document.createElement('div');
                tenFolderDiv.classList.add('ten-folder');
  

                const folderNameElement = document.createElement('p');
                folderNameElement.textContent = folderName;
  

                const chevronIcon = document.createElement('i');
                chevronIcon.classList.add('fa', 'fa-solid', 'fa-chevron-right');
  
 
                tenFolderDiv.appendChild(folderNameElement);
                tenFolderDiv.appendChild(chevronIcon);
  

                folderRightTim.appendChild(tenFolderDiv);
              }
            });
          }
        } else {
          console.warn(`Folder with id ${folderId} not found in Results array.`);
        }
        const folderRightConten = document.querySelector('.folder-right-conten');
        if (folderRightConten) {
            folderRightConten.setAttribute('id-khai', folderId.toString());
        }
      });
  
 
    document.body.addEventListener('click', (event) => {
      const target = event.target as HTMLElement;
      const isFolderCha = target.closest('.folder-cha');
      const isTrElement = target.closest('tr');
      const isDocument = target.closest('.document');

      if (!isFolderCha && !isTrElement && !isDocument) {
 
        const selectedItems = document.querySelectorAll('.selected');
        selectedItems.forEach(item => item.classList.remove('selected'));
      }
    });
      this.renderer.listen(row, 'click', () => {
        const clickedFolderPath = row.dataset.folderPath; 
  
      });
    });
  }

  appendToTable(folders: Folders[], documents: Document[], folderId: number): void {
    const tbody = document.querySelector('.folder-right-conten table tbody') as HTMLElement;
    if (tbody) {
      // Xóa nội dung cũ của tbody
      while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
      }
  
      folders.forEach(folder => {
        const folderRow = document.createElement('tr');
        folderRow.classList.add('folder');
        folderRow.setAttribute('data-folder-id', folder.id.toString());
  
        folderRow.innerHTML = `
          <th><i class="fa-solid fa-folder"></i> 
              <p>${folder.name}</p>
          </th>
          <th>Data modified</th>
          <th>Type</th>
          <th>Size</th>
        `;
  
        // Sử dụng Renderer2 để thêm sự kiện dblclick
        this.renderer.listen(folderRow, 'dblclick', () => {
          this.loadFolderContents(folder.id); 
          this.displayFolderPath(folder.path);
  
          const folderDropArea = document.getElementById('folderDropArea');
          if (folderDropArea) {
            this.renderer.setAttribute(folderDropArea, 'id-khai', folder.id.toString());
          }
        });
  
        this.renderer.appendChild(tbody, folderRow);
      });
  
      documents.forEach(doc => {
        const documentRow = document.createElement('tr');
        documentRow.classList.add('document');
        documentRow.setAttribute('data-document-id', doc.id.toString());
  
        documentRow.innerHTML = `
          <th>
            <a>
              <img class="card-img doc-img rounded-top" [class.inverted]="getIsThumbInverted()" src="${this.baseUrl}documents/${doc.id}/thumb/">
              <p>${doc.filename}</p>
            </a>
          </th>
          <th>${doc.archive_filename}</th>
          <th>${doc.checksum}</th>
          <th>${doc.document}img</th>
        `;
  
        // Sử dụng Renderer2 để thêm sự kiện dblclick
        this.renderer.listen(documentRow, 'dblclick', () => {
          this.router.navigate(['/documents', doc.id]);
          const folder = this.findFolderById(doc.folder);
          if (folder) {
            const folderDropArea = document.getElementById('folderDropArea');
            if (folderDropArea) {
              this.renderer.setAttribute(folderDropArea, 'id-khai', folder.id.toString());
            }
          }
        });
  
        this.renderer.appendChild(tbody, documentRow);
      });
    }
  }

}