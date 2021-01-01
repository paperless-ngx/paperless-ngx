import { TestBed } from '@angular/core/testing';

import { AppViewService } from './app-view.service';

describe('AppViewService', () => {
  let service: AppViewService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(AppViewService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
