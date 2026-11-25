// "Curso Vinculado" (issues #37 and #25): show the saved course label whenever
// the form holds a course, and the search only while the user is changing it
// or there is no course yet. Derived from the current form data instead of
// from a value read once on mount, so a draft loaded after the step mounted
// still shows its course.
export const showCourseSearch = ({ courseId, editing }) => Boolean(editing) || !courseId;
