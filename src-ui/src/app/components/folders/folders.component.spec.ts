import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router'
import { NgbModal, NgbModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { Subject, of, throwError } from 'rxjs'
import { Folder } from 'src/app/data/folder'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { FolderService } from 'src/app/services/rest/folder.service'
import { ToastService } from 'src/app/services/toast.service'
import { FoldersComponent } from './folders.component'

const tree: Folder[] = [
  {
    id: 1,
    name: 'Inbox',
    is_default: true,
    parent: null,
    document_count: 2,
    children: [
      {
        id: 2,
        name: 'Taxes',
        parent: 1,
        document_count: 0,
        children: [],
      },
    ],
  },
  {
    id: 3,
    name: 'Work',
    parent: null,
    document_count: 0,
    children: [],
  },
]

describe('FoldersComponent', () => {
  let component: FoldersComponent
  let fixture: ComponentFixture<FoldersComponent>
  let folderService: FolderService
  let documentService: DocumentService
  let toastService: ToastService
  let modalService: NgbModal
  let permissionsService: PermissionsService

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [
        NgbModule,
        NgxBootstrapIconsModule.pick(allIcons),
        FoldersComponent,
      ],
      providers: [
        {
          provide: PermissionsService,
          useValue: {
            currentUserCan: () => true,
            currentUserHasObjectPermissions: () => true,
            currentUserOwnsObject: () => true,
          },
        },
        {
          provide: ActivatedRoute,
          useValue: { paramMap: of(convertToParamMap({})) },
        },
        { provide: Router, useValue: { navigate: jest.fn() } },
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    folderService = TestBed.inject(FolderService)
    documentService = TestBed.inject(DocumentService)
    toastService = TestBed.inject(ToastService)
    modalService = TestBed.inject(NgbModal)
    permissionsService = TestBed.inject(PermissionsService)

    jest
      .spyOn(folderService, 'getTree')
      .mockReturnValue(of({ count: 2, all: [1, 3], results: tree }) as any)
    jest
      .spyOn(documentService, 'list')
      .mockReturnValue(of({ count: 0, all: [], results: [] }) as any)

    fixture = TestBed.createComponent(FoldersComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should load and flatten the folder tree', () => {
    expect(component.roots.length).toEqual(2)
    expect(component.flatFolders.length).toEqual(3)
    expect(component.visibleFlatFolders.length).toEqual(3)
    expect(component.foldersById.get(2)?.name).toEqual('Taxes')
    expect(component.foldersById.get(2)?.depth).toEqual(1)
  })

  it('should collapse and expand folder branches', () => {
    const inbox = component.foldersById.get(1)!
    component.toggleFolderCollapsed(inbox)
    expect(component.visibleFlatFolders.map((f) => f.id)).toEqual([1, 3])
    component.toggleFolderCollapsed(inbox)
    expect(component.visibleFlatFolders.map((f) => f.id)).toEqual([1, 2, 3])
  })

  it('should show root folders when no folder is selected', () => {
    component.openFolder(null)
    expect(component.subfolders.length).toEqual(2)
    expect(component.documents.length).toEqual(0)
  })

  it('should load documents when navigating into a folder', () => {
    const listSpy = jest.spyOn(documentService, 'list')
    component.openFolder(component.foldersById.get(1))
    expect(listSpy).toHaveBeenCalled()
    expect(component.currentFolder?.id).toEqual(1)
    expect(component.subfolders.length).toEqual(1)
  })

  it('should compute breadcrumb', () => {
    component.openFolder(component.foldersById.get(2))
    expect(component.breadcrumb.map((f) => f.name)).toEqual(['Inbox', 'Taxes'])
  })

  it('should toggle document selection', () => {
    const doc = { id: 5, title: 'doc' } as any
    component.toggleSelected(doc)
    expect(component.isSelected(doc)).toBeTruthy()
    component.toggleSelected(doc)
    expect(component.isSelected(doc)).toBeFalsy()
  })

  it('should move documents via bulk edit', () => {
    const bulkSpy = jest
      .spyOn(documentService, 'bulkEdit')
      .mockReturnValue(of(true) as any)
    component.openFolder(component.foldersById.get(1))
    component.moveDocsTo(2, [10, 11])
    expect(bulkSpy).toHaveBeenCalledWith(
      { documents: [10, 11] },
      'set_folder',
      {
        folder: 2,
      }
    )
  })

  it('should open a create dialog', () => {
    const modalSpy = jest.spyOn(modalService, 'open').mockReturnValue({
      componentInstance: { succeeded: of(null) },
    } as any)
    component.createFolder(null)
    expect(modalSpy).toHaveBeenCalled()
  })

  it('prevents duplicate moves while a request is pending', () => {
    const pending = new Subject()
    const bulkSpy = jest
      .spyOn(documentService, 'bulkEdit')
      .mockReturnValue(pending)
    component.moveDocsTo(2, [10])
    component.moveDocsTo(3, [10])
    expect(bulkSpy).toHaveBeenCalledTimes(1)
    expect(component.moving).toBe(true)
    pending.complete()
    expect(component.moving).toBe(false)
  })

  it('keeps selection when moving fails so the user can retry', () => {
    jest
      .spyOn(documentService, 'bulkEdit')
      .mockReturnValue(throwError(() => new Error('offline')))
    jest.spyOn(toastService, 'showError').mockImplementation(() => {})
    component.selected.add(10)
    component.moveDocsTo(2, [10])
    expect(component.selected.has(10)).toBe(true)
    expect(component.moving).toBe(false)
  })

  it('clears selection on page changes', () => {
    component.selected.add(10)
    component.onPageChange(2)
    expect(component.selected.size).toBe(0)
  })

  it('moves the selected group when dragging a selected document', () => {
    const bulkSpy = jest
      .spyOn(documentService, 'bulkEdit')
      .mockReturnValue(of(true))
    component.openFolder(tree[0], false)
    component.selected = new Set([10, 11])
    component.onDocDragStart(
      { dataTransfer: { setData: jest.fn() } } as any,
      { id: 10 } as any
    )
    const event = {
      preventDefault: jest.fn(),
      stopPropagation: jest.fn(),
      dataTransfer: {},
    } as any
    component.onFolderDragOver(event, tree[1])
    expect(component.dropTarget).toBe(3)
    component.onFolderDrop(event, tree[1])
    expect(bulkSpy).toHaveBeenCalledWith(
      { documents: [10, 11] },
      'set_folder',
      { folder: 3 }
    )
    expect(component.dropTarget).toBeNull()
  })

  it('ignores cancelled drags and moves to the current folder', () => {
    const bulkSpy = jest.spyOn(documentService, 'bulkEdit')
    component.openFolder(tree[0], false)
    component.moveDocsTo(1, [10])
    component.onDocDragStart(
      { dataTransfer: { setData: jest.fn() } } as any,
      { id: 10 } as any
    )
    component.onDragEnd()
    component.onFolderDrop(
      { preventDefault: jest.fn(), stopPropagation: jest.fn() } as any,
      tree[1]
    )
    expect(bulkSpy).not.toHaveBeenCalled()
  })

  it('does not select documents without change permission', () => {
    jest
      .spyOn(permissionsService, 'currentUserHasObjectPermissions')
      .mockReturnValue(false)
    component.documents = [{ id: 10 } as any]
    component.toggleSelectAll()
    expect(component.selected.size).toBe(0)
    component.toggleSelected(component.documents[0])
    expect(component.selected.size).toBe(0)
  })

  it('ignores a previous folder response after navigation', () => {
    const pending = new Subject<any>()
    jest.spyOn(documentService, 'list').mockReturnValue(pending)
    component.openFolder(tree[0], false)
    component.openFolder(null, false)
    pending.next({ count: 1, results: [{ id: 10 }] })
    expect(component.documents).toEqual([])
    expect(component.documentsLoading).toBe(false)
  })

  it('should edit name and parent in a single folder dialog', () => {
    const modalSpy = jest.spyOn(modalService, 'open').mockReturnValue({
      componentInstance: { succeeded: of(null) },
    } as any)
    component.renameFolder(component.foldersById.get(3)!)
    expect(modalSpy).toHaveBeenCalled()
    expect(
      (modalSpy.mock.results[0].value as any).componentInstance.folders
    ).toEqual(component.roots)
  })

  it('should delete a folder', () => {
    const delSpy = jest
      .spyOn(folderService, 'delete')
      .mockReturnValue(of(true) as any)
    const toastSpy = jest.spyOn(toastService, 'showInfo')
    component.deleteFolder(tree[1])
    expect(delSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should not allow deleting the default folder', () => {
    expect(component.canDeleteFolder(component.foldersById.get(1))).toBeFalsy()
    expect(component.canDeleteFolder(component.foldersById.get(3))).toBeTruthy()
  })

  it('should require global delete permission to delete folders', () => {
    jest.spyOn(permissionsService, 'currentUserCan').mockReturnValue(false)
    expect(component.canDeleteFolder(component.foldersById.get(3))).toBeFalsy()
  })
})
