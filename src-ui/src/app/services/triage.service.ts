import { Injectable, inject } from '@angular/core'
import { BehaviorSubject, Observable } from 'rxjs'
import { Document } from '../data/document'
import { FilterRule } from '../data/filter-rule'

export interface TriageState {
  documents: Document[]
  currentIndex: number
  filterRules: FilterRule[]
  returnUrl: string
}

export interface UndoAction {
  documentId: number
  previousValues: Partial<Document>
  actionType: 'metadata' | 'archive'
}

/**
 * Service to manage the triage mode state, queue, and undo functionality
 */
@Injectable({
  providedIn: 'root',
})
export class TriageService {
  private triageStateSubject = new BehaviorSubject<TriageState | null>(null)
  public triageState$: Observable<TriageState | null> =
    this.triageStateSubject.asObservable()

  private undoStack: UndoAction[] = []

  /**
   * Initialize triage mode with a list of documents and filter rules
   */
  initializeTriage(
    documents: Document[],
    filterRules: FilterRule[],
    returnUrl: string
  ): void {
    this.triageStateSubject.next({
      documents,
      currentIndex: 0,
      filterRules,
      returnUrl,
    })
    this.undoStack = []
  }

  /**
   * Get the current triage state
   */
  getState(): TriageState | null {
    return this.triageStateSubject.value
  }

  /**
   * Get the current document being triaged
   */
  getCurrentDocument(): Document | null {
    const state = this.triageStateSubject.value
    if (!state || state.currentIndex >= state.documents.length) {
      return null
    }
    return state.documents[state.currentIndex]
  }

  /**
   * Move to the next document in the queue
   */
  next(): void {
    const state = this.triageStateSubject.value
    if (!state) return

    const newIndex = Math.min(
      state.currentIndex + 1,
      state.documents.length - 1
    )
    this.triageStateSubject.next({
      ...state,
      currentIndex: newIndex,
    })
  }

  /**
   * Move to the previous document in the queue
   */
  previous(): void {
    const state = this.triageStateSubject.value
    if (!state) return

    const newIndex = Math.max(state.currentIndex - 1, 0)
    this.triageStateSubject.next({
      ...state,
      currentIndex: newIndex,
    })
  }

  /**
   * Remove a document from the queue (after archiving)
   */
  removeCurrentDocument(): void {
    const state = this.triageStateSubject.value
    if (!state) return

    const newDocuments = [...state.documents]
    newDocuments.splice(state.currentIndex, 1)

    // If we removed the last document, move index back
    const newIndex =
      state.currentIndex >= newDocuments.length
        ? Math.max(newDocuments.length - 1, 0)
        : state.currentIndex

    this.triageStateSubject.next({
      ...state,
      documents: newDocuments,
      currentIndex: newIndex,
    })
  }

  /**
   * Update the current document in the queue
   */
  updateCurrentDocument(updatedDoc: Document): void {
    const state = this.triageStateSubject.value
    if (!state) return

    const newDocuments = [...state.documents]
    newDocuments[state.currentIndex] = updatedDoc

    this.triageStateSubject.next({
      ...state,
      documents: newDocuments,
    })
  }

  /**
   * Push an action to the undo stack
   */
  pushUndoAction(action: UndoAction): void {
    this.undoStack.push(action)
    // Keep only the last 10 actions to prevent memory issues
    if (this.undoStack.length > 10) {
      this.undoStack.shift()
    }
  }

  /**
   * Get the last undo action
   */
  getLastUndoAction(): UndoAction | null {
    return this.undoStack.length > 0
      ? this.undoStack[this.undoStack.length - 1]
      : null
  }

  /**
   * Pop the last undo action from the stack
   */
  popUndoAction(): UndoAction | null {
    return this.undoStack.pop() || null
  }

  /**
   * Check if there are any undo actions available
   */
  canUndo(): boolean {
    return this.undoStack.length > 0
  }

  /**
   * Check if the queue is empty
   */
  isEmpty(): boolean {
    const state = this.triageStateSubject.value
    return !state || state.documents.length === 0
  }

  /**
   * Get the number of remaining documents
   */
  getRemainingCount(): number {
    const state = this.triageStateSubject.value
    return state ? state.documents.length : 0
  }

  /**
   * Clear triage state
   */
  clear(): void {
    this.triageStateSubject.next(null)
    this.undoStack = []
  }
}

