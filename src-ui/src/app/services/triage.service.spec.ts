import { TestBed } from '@angular/core/testing'
import { TriageService } from './triage.service'
import { Document } from '../data/document'
import { FilterRule } from '../data/filter-rule'

describe('TriageService', () => {
  let service: TriageService

  beforeEach(() => {
    TestBed.configureTestingModule({})
    service = TestBed.inject(TriageService)
  })

  it('should be created', () => {
    expect(service).toBeTruthy()
  })

  describe('initializeTriage', () => {
    it('should initialize triage state', () => {
      const documents: Document[] = [
        { id: 1, title: 'Doc 1' } as Document,
        { id: 2, title: 'Doc 2' } as Document,
      ]
      const filterRules: FilterRule[] = []
      const returnUrl = '/documents'

      service.initializeTriage(documents, filterRules, returnUrl)

      const state = service.getState()
      expect(state).toBeTruthy()
      expect(state.documents.length).toBe(2)
      expect(state.currentIndex).toBe(0)
      expect(state.returnUrl).toBe(returnUrl)
    })

    it('should clear undo stack on initialization', () => {
      service.pushUndoAction({
        documentId: 1,
        previousValues: {},
        actionType: 'metadata',
      })

      expect(service.canUndo()).toBe(true)

      const documents: Document[] = [{ id: 1, title: 'Doc 1' } as Document]
      service.initializeTriage(documents, [], '/documents')

      expect(service.canUndo()).toBe(false)
    })
  })

  describe('getCurrentDocument', () => {
    it('should return current document', () => {
      const documents: Document[] = [
        { id: 1, title: 'Doc 1' } as Document,
        { id: 2, title: 'Doc 2' } as Document,
      ]
      service.initializeTriage(documents, [], '/documents')

      const currentDoc = service.getCurrentDocument()
      expect(currentDoc).toBeTruthy()
      expect(currentDoc.id).toBe(1)
    })

    it('should return null when no state', () => {
      expect(service.getCurrentDocument()).toBeNull()
    })
  })

  describe('next and previous', () => {
    beforeEach(() => {
      const documents: Document[] = [
        { id: 1, title: 'Doc 1' } as Document,
        { id: 2, title: 'Doc 2' } as Document,
        { id: 3, title: 'Doc 3' } as Document,
      ]
      service.initializeTriage(documents, [], '/documents')
    })

    it('should move to next document', () => {
      service.next()
      const currentDoc = service.getCurrentDocument()
      expect(currentDoc.id).toBe(2)
    })

    it('should not go beyond last document', () => {
      service.next()
      service.next()
      service.next()
      const state = service.getState()
      expect(state.currentIndex).toBe(2)
    })

    it('should move to previous document', () => {
      service.next()
      service.previous()
      const currentDoc = service.getCurrentDocument()
      expect(currentDoc.id).toBe(1)
    })

    it('should not go before first document', () => {
      service.previous()
      const state = service.getState()
      expect(state.currentIndex).toBe(0)
    })
  })

  describe('removeCurrentDocument', () => {
    it('should remove current document from queue', () => {
      const documents: Document[] = [
        { id: 1, title: 'Doc 1' } as Document,
        { id: 2, title: 'Doc 2' } as Document,
        { id: 3, title: 'Doc 3' } as Document,
      ]
      service.initializeTriage(documents, [], '/documents')

      service.removeCurrentDocument()

      const state = service.getState()
      expect(state.documents.length).toBe(2)
      expect(state.documents[0].id).toBe(2)
    })

    it('should adjust index when removing last document', () => {
      const documents: Document[] = [
        { id: 1, title: 'Doc 1' } as Document,
        { id: 2, title: 'Doc 2' } as Document,
      ]
      service.initializeTriage(documents, [], '/documents')
      service.next()

      service.removeCurrentDocument()

      const state = service.getState()
      expect(state.currentIndex).toBe(0)
    })
  })

  describe('undo stack', () => {
    it('should push undo actions', () => {
      const action = {
        documentId: 1,
        previousValues: { tags: [1, 2] },
        actionType: 'metadata' as const,
      }

      service.pushUndoAction(action)

      expect(service.canUndo()).toBe(true)
      expect(service.getLastUndoAction()).toEqual(action)
    })

    it('should pop undo actions', () => {
      const action = {
        documentId: 1,
        previousValues: {},
        actionType: 'metadata' as const,
      }

      service.pushUndoAction(action)
      const popped = service.popUndoAction()

      expect(popped).toEqual(action)
      expect(service.canUndo()).toBe(false)
    })

    it('should limit undo stack to 10 items', () => {
      for (let i = 0; i < 15; i++) {
        service.pushUndoAction({
          documentId: i,
          previousValues: {},
          actionType: 'metadata',
        })
      }

      let count = 0
      while (service.canUndo()) {
        service.popUndoAction()
        count++
      }

      expect(count).toBe(10)
    })
  })

  describe('isEmpty and getRemainingCount', () => {
    it('should return true when no documents', () => {
      expect(service.isEmpty()).toBe(true)
      expect(service.getRemainingCount()).toBe(0)
    })

    it('should return correct count', () => {
      const documents: Document[] = [
        { id: 1, title: 'Doc 1' } as Document,
        { id: 2, title: 'Doc 2' } as Document,
      ]
      service.initializeTriage(documents, [], '/documents')

      expect(service.isEmpty()).toBe(false)
      expect(service.getRemainingCount()).toBe(2)
    })
  })

  describe('clear', () => {
    it('should clear all state', () => {
      const documents: Document[] = [{ id: 1, title: 'Doc 1' } as Document]
      service.initializeTriage(documents, [], '/documents')
      service.pushUndoAction({
        documentId: 1,
        previousValues: {},
        actionType: 'metadata',
      })

      service.clear()

      expect(service.getState()).toBeNull()
      expect(service.canUndo()).toBe(false)
    })
  })
})

