import { Component, OnInit, Renderer2, ElementRef,ViewChild } from '@angular/core';
import { FoldersService } from 'src/app/services/rest/folders.service';
import { Document, Folders, Results,SRC  } from 'src/app/data/folders';
import { PreventRightClickDirective } from 'src/app/services/prevent-right-click.directive';
import { ChangeDetectorRef } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http'; 
import { HttpClient } from '@angular/common/http';
import { environment } from 'src/environments/environment'
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



  

  constructor(
    private foldersService: FoldersService, 
    private renderer: Renderer2, 
    private elementRef: ElementRef,
    private cdr: ChangeDetectorRef,
    private http: HttpClient
  ) {}

 ngOnInit(): void {
  this.addGridStyles();
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
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.renderer.addClass(this.elementRef.nativeElement, 'drag-over');
  }

  onDragLeave(event: DragEvent): void {
    this.renderer.removeClass(this.elementRef.nativeElement, 'drag-over');
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      const folderId = parseInt(this.folderRightContent.nativeElement.getAttribute('id-khai') || '', 10);
      if (!isNaN(folderId) && folderId > 0) {
        const formData = new FormData();
        formData.append('file', file);

        // Log id-khai before uploading
        console.log('id-khai khi kéo file vào:', folderId);

        // Call your service method to upload the document
        this.uploadDocument(formData, folderId);
      } else {
        console.error('Không thể lấy mã từ id-khai của phần tử hoặc id-khai không hợp lệ.');
      }
    }
  }

  uploadDocument(formData: FormData, folderId: number): void {
    formData.append('folder', folderId.toString()); // Ensure 'folder' field is appended correctly
    console.log('Dữ liệu FormData trước khi tải lên:', formData.get('file'), formData.get('folder')); // Log to verify FormData content

    this.foldersService.uploadDocument(formData).subscribe(
      (response: Document) => {
        console.log('Tải tệp lên thành công:', response);
        this.uploadedDocuments.push(response);
        // Handle successful upload here if needed
      },
      (error) => {
        console.error('Lỗi khi tải tệp lên:', error);
        // Handle upload error here if needed
      }
    );
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
  
  onCutClickf(event: Event) {
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
    if (this.pasteElementf && this.cutItemIdf !== null) {
      const addValue = this.pasteElementf.nativeElement.getAttribute('add');
      if (addValue !== null && addValue !== '') {
        const newParentFileId = parseInt(addValue, 10);
        console.log('Paste element attribute (chua):', addValue);
        console.log('New parent file ID:', newParentFileId);
  
        const fileToUpdate = this.documents.find(document => document.id === this.cutItemIdf);
        if (fileToUpdate) {
          console.log('File to update:', fileToUpdate);
  

          const updateData = { folder: newParentFileId };
          console.log('Sending update data:', updateData);
  
          this.foldersService.updateFile(fileToUpdate.id, updateData).subscribe(updatedFile => {
            console.log('Updated file:', updatedFile);
            fileToUpdate.folder = updatedFile.folder; 
  
          }, error => {
            console.error('Failed to update folder:', error);
            
          });
        }
      }
    }
  }
  

  
  onCutClick() {
    if (this.cutElement) {
      const addValue = this.cutElement.nativeElement.getAttribute('add');
      this.cutItemId = parseInt(addValue, 10); 
    }
  }
  
  // Hàm dán (paste)
  onPasteClick() {
    if (this.pasteElement && this.cutItemId !== null) {
      const addValue = this.pasteElement.nativeElement.getAttribute('add');
      const newParentFolderId = parseInt(addValue, 10);
  
      const folderToUpdate = this.results.find(result => result.id === this.cutItemId);
      if (folderToUpdate) {
        this.foldersService.updateFolder(folderToUpdate.id, { parent_folder: newParentFolderId }).subscribe(updatedFolder => {
          folderToUpdate.parent_folder = newParentFolderId; 
          this.cutItemId = null; 
        }, error => {
          console.error('Failed to update folder:', error); 
        });
      }
    }
  }
  

  // Hàm đảo ngược trạng thái hiển thị của một phần tử
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
      // Gọi service để xóa nhiều ID từ server
      this.foldersService.bulkDeleteFolders(idsToDelete).subscribe(
        () => {
          // Xóa các ID khỏi mảng results
          this.results = this.results.filter(result => !idsToDelete.includes(result.id));
          console.log(`IDs ${idsToDelete.join(', ')} have been deleted.`);
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
      // Gọi service để xóa ID từ server
      this.foldersService.deleteFolder(idToDelete).subscribe(
        () => {
          // Xóa ID khỏi mảng results
          this.results = this.results.filter(result => result.id !== idToDelete);
          console.log(`ID ${idToDelete} has been deleted.`);
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
            }
          }, error => {
            console.error('Error updating folder:', error);
            // Handle error if needed
          });
      }
    }
  }
  
  
  
  
  loadFolders(): void {
    this.foldersService.getResults().subscribe(response => {
      this.results = response.results;
    });
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
              }
            },
            error => {
              console.error('Error updating file:', error);
              // Handle error if needed
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
      });
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
  loadFolderContents(folderId: number): void {
    this.foldersService.fetchfolderandDocuments(folderId).subscribe({
      next: (data: { documents: Document[], folders: Folders[] }) => {
        this.folders = data.folders;
        this.documents = data.documents;
        this.initializeFolders();
        this.initializeDocuments();
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
      },
      error: (error: HttpErrorResponse) => {
        console.error('Error fetching folder contents:', error);
      }
    });
  }
  initializeFolders(): void {
    const foldersContainer = this.elementRef.nativeElement.querySelector('#folders-container');
    if (foldersContainer) {
      // Kết hợp `folders` và `results` thành một mảng duy nhất
      const allFolders = [...this.folders, ...this.results];
      foldersContainer.innerHTML = '';
  
      // Map để lưu trữ các thư mục theo `parent ID`
      const folderMap = new Map<number, Folders[]>();
  
      // Nhóm các thư mục theo `parent ID`
      allFolders.forEach(folder => {
        const parentId = folder.parent_folder ?? null;
        if (!folderMap.has(parentId)) {
          folderMap.set(parentId, []);
        }
        folderMap.get(parentId)?.push(folder);
      });
  
      // Map để lưu trữ các tài liệu theo `folder ID`
      const documentMap = new Map<number, Document[]>();
  
      // Nhóm các tài liệu theo `folder ID`
      this.thesis.forEach(document => {
        if (document.folder !== null && document.folder !== undefined) {
          const folderId = document.folder;
          if (!documentMap.has(folderId)) {
            documentMap.set(folderId, []);
          }
          documentMap.get(folderId)?.push(document);
        }
      });
  
      // Hàm đệ quy để tạo thư mục và tài liệu của chúng
      const createFolders = (parentId: number | null, parentDiv: HTMLElement | null): void => {
        const children = folderMap.get(parentId) || [];
        children.forEach(folder => {
          const folderHTML = this.createFolderHTML(folder);
          if (parentDiv) {
            this.renderer.appendChild(parentDiv, folderHTML);
          } else {
            this.renderer.appendChild(foldersContainer, folderHTML);
          }
  
          // Thêm tài liệu vào thư mục này
          const documents = documentMap.get(folder.id) || [];
          const childrenContainer = folderHTML.querySelector('.children-container') as HTMLElement;
          documents.forEach(document => {
            const documentHTML = this.createDocumentHTML(document);
            this.renderer.appendChild(childrenContainer, documentHTML);
          });
  
          // Đệ quy tạo các thư mục con
          createFolders(folder.id, folderHTML.querySelector('.children-container') as HTMLElement);
        });
      };
  
      // Bắt đầu tạo thư mục từ gốc (parentId = null)
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
  
   // Method to handle folder click event
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

displayFolderPath(path: string): void {
  const folderRightTim = this.elementRef.nativeElement.querySelector('.folder-right-tim');
  if (folderRightTim) {
    // Clear previous content
    folderRightTim.innerHTML = '';

    const pathSegments = path.split('/');

    // Create logo-folder div
    const logoFolderDiv = document.createElement('div');
    logoFolderDiv.classList.add('logo-folder');
    logoFolderDiv.innerHTML = `
      <i class="fa-solid fa-folder"></i> <i class="fa-solid fa-chevron-right"></i>
    `;
    folderRightTim.appendChild(logoFolderDiv);

    // Iterate through path segments to create and append folderDivs
    pathSegments.forEach((segment, index) => {
      const folderId = parseInt(segment, 10);
      const folder = this.findFolderById(folderId);

      // Ensure folder is valid before using its properties
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

        // Add click event listener to each folderDiv
        folderDiv.addEventListener('click', () => {
          this.handleFolderClick(folderId); // Update path and folder contents on click
        });
      } else {
        console.error(`Folder not found for ID: ${folderId}`);
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
  
// Xóa lớp 'selected' khỏi tất cả các phần tử đã chọn nếu không giữ Ctrl
      if (!(event as MouseEvent).ctrlKey) {
        const selectedItems = document.querySelectorAll('.selected');
        selectedItems.forEach(item => item.classList.remove('selected'));
      }

      // Thêm hoặc xóa lớp 'selected' cho phần tử được click
      folderDiv.classList.toggle('selected');
    
      // Hiển thị nội dung của thư mục và đường dẫn
      this.foldersService.fetchfolderandDocuments(clickedFolderId).subscribe({
        next: (data) => {
          this.appendToTable(data.folders, data.documents, clickedFolderId);
          this.displayFolderPath(clickedFolderPath);
        },
        error: (error) => {
          console.error('Error fetching folder and documents:', error);
        }
      });
    });
  
    // Sự kiện click trên folderIcon để mở/đóng children-container
    this.renderer.listen(folderIcon, 'click', (event: Event) => {
      event.stopPropagation(); // Ngăn sự kiện click lan ra ngoài
  
      if (childrenContainer.style.display === 'none') {
        childrenContainer.style.display = 'block';
        folderIcon.style.transform = 'rotate(90deg)';
        folderIconFolder.classList.replace('fa-folder', 'fa-folder-open');
  
        // Xóa hết các thành phần cũ trong childrenContainer trước khi gọi API
        childrenContainer.innerHTML = '';
  
        // Gọi API để lấy dữ liệu folders và documents
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
  
    // Sự kiện click để hiển thị đường dẫn thư mục và cập nhật id-khai attribute
    this.renderer.listen(folderHeader, 'click', () => {
      const clickedFolderPath = folder.path;
      const folderRightTim = document.querySelector('.folder-right-tim');
      if (folderRightTim) {
        folderRightTim.innerHTML = '';
  
        const logoFolderDiv = document.createElement('div');
        logoFolderDiv.classList.add('logo-folder');
  
        const folderIcon = document.createElement('i');
        folderIcon.classList.add('fa', 'fa-solid', 'fa-folder');
  
        const chevronIcon = document.createElement('i');
        chevronIcon.classList.add('fa', 'fa-solid', 'fa-chevron-right');
  
        logoFolderDiv.appendChild(folderIcon);
        logoFolderDiv.appendChild(chevronIcon);
  
        folderRightTim.appendChild(logoFolderDiv);
  
        const pathNumbers = clickedFolderPath.split('/').filter(part => part !== '');
  
        pathNumbers.forEach(number => {
          const folderId = parseInt(number, 10);
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
  
      this.loggedFolderPath = clickedFolderPath;
  
      this.displayFolderContents(folder.id);
  
      // Update id-khai attribute dynamically
      const folderRightConten = document.querySelector('.folder-right-conten');
      if (folderRightConten) {
        folderRightConten.setAttribute('id-khai', folder.id.toString());
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
          // Remove 'selected' class from all previously selected items
          const selectedItems = document.querySelectorAll('.selected');
          selectedItems.forEach(item => item.classList.remove('selected'));
        }
        // Toggle 'selected' class on the clicked item
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
  
    // Click event listener to deselect when clicking outside
    document.body.addEventListener('click', (event) => {
      const target = event.target as HTMLElement;
      const isFolderCha = target.closest('.folder-cha');
      const isTrElement = target.closest('tr');
      const isDocument = target.closest('.document');

      if (!isFolderCha && !isTrElement && !isDocument) {
        // Remove 'selected' class from all previously selected items
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
      tbody.innerHTML = '';
      folders.forEach(folder => {
        const folderRow = document.createElement('tr');
        folderRow.classList.add('folder');
        folderRow.dataset.folderId = folder.id.toString();
  
        folderRow.innerHTML = `
          <th><i class="fa-solid fa-folder"></i> 
              <p>${folder.name}</p>
          </th>
          <th>Data modified</th>
          <th>Type</th>
          <th>Size</th>
        `;
  
        // Thêm sự kiện dblclick
        this.renderer.listen(folderRow, 'dblclick', () => {
          this.loadFolderContentss(folder.id); // Gọi hàm loadFolderContents với ID của folder
          this.displayFolderPath(folder.path); // Hiển thị đường dẫn của folder khi double click
        });
  
        this.renderer.appendChild(tbody, folderRow);
      });
  
      // Thêm các thẻ tr cho từng document
      documents.forEach(doc => {
        const documentRow = document.createElement('tr');
        documentRow.classList.add('document');
        documentRow.dataset.documentId = doc.id.toString();
  
        documentRow.innerHTML = `
          <th routerLink="/documents/${doc.id}"><img class="card-img doc-img rounded-top" [class.inverted]="getIsThumbInverted()" src="${this.baseUrl}documents/${doc.id}/thumb/">
              <p>${doc.filename}</p>
          </th>
          <th>${doc.archive_filename}</th>
          <th>${doc.checksum}</th>
          <th>${doc.document}img</th>
        `;
  
        // Thêm sự kiện dblclick
        this.renderer.listen(documentRow, 'dblclick', () => {
          // Giả sử doc có thuộc tính folderId
          this.loadFolderContentss(doc.id);
          // Hiển thị đường dẫn của folder chứa document khi double click
          const folder = this.findFolderById(doc.folder);
          if (folder) {
            this.displayFolderPath(folder.path);
          }
        });
  
        this.renderer.appendChild(tbody, documentRow);
      });
    }
  }
  
  
}