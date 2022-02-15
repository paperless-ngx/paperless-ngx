import { CustomDatePipe } from './custom-date.pipe';

describe('CustomDatePipe', () => {
  it('create an instance', () => {
    const pipe = new CustomDatePipe();
    expect(pipe).toBeTruthy();
  });
});
