/**
 * Converts a Date object to ISO string in UTC format
 * Preserves the local time values by offsetting the timezone difference
 */
const formatDateForMongoDB = (date) => {
  // Create a new date with the timezone offset applied
  // This will preserve the local time values when converted to UTC
  const userTimezoneOffset = date.getTimezoneOffset() * 60000;
  const localISOTime = new Date(
    date.getTime() - userTimezoneOffset
  ).toISOString();
  return localISOTime;
};

export { formatDateForMongoDB };
